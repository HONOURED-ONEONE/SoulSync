from sqlalchemy.orm import Session
from ..models import Mission, MissionAssignment, Profile, PlanRun, User, AuditLog
from datetime import date, datetime, timedelta
import json
from .gemini_client import call_gemini_json

ALLOWED_MISSION_TYPES = ["study", "fitness", "sleep", "nutrition", "reflection", "social", "chores"]
WIND_DOWN_TYPES = ["reflection", "sleep"]
ACTIVE_TYPES = ["study", "fitness", "chores", "social", "nutrition"]
UNSAFE_KEYWORDS = ["adult", "violence", "sexual", "explicit"]

# --- Micro policy constants ---
MICRO_XP_DEFAULT = 2              # small reward if micro mission lacks explicit xp
MICRO_DAILY_CAP = 10              # optional cap per day (applies to total micro XP awards)
MICRO_MAX_PER_PARENT = 1          # micro click once per parent (anti-spam)
MICRO_ALLOWED_TYPES_AFTER_BEDTIME = set(["reflection", "sleep"])
MICRO_MAX_DURATION_AFTER_BEDTIME = 15


def can_mark_micro_now(micro_assign: MissionAssignment, time_context: dict, db: Session) -> tuple:
    """
    Returns (ok: bool, reason: str). Enforces after-bedtime micro constraints:
      - Only micro linked to reflection or sleep parent type
      - Duration <= 15
      - Difficulty 'easy' (micro missions are created 'easy' by default)
    """
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    mission = db.query(Mission).filter(Mission.id == micro_assign.mission_id).first()
    if not mission:
        return False, "Mission not found."

    if (mission.type or "").lower() != "micro":
        # Not a micro mission—this helper is only for micros
        return False, "Not a micro mission."

    meta = mission.geo_rule_json or {}
    parent_type = (meta.get("parent_type") or "").lower()
    dur = int(mission.duration_minutes or 0)

    if after_bedtime:
        if parent_type not in MICRO_ALLOWED_TYPES_AFTER_BEDTIME:
            return False, f"After bedtime: only reflection/sleep micros allowed (parent type '{parent_type}')."
        if dur > MICRO_MAX_DURATION_AFTER_BEDTIME:
            return False, f"After bedtime: micro duration must be <= {MICRO_MAX_DURATION_AFTER_BEDTIME} mins (got {dur})."

    return True, ""


def award_micro_xp(user_id: int, mission: Mission, db: Session) -> None:
    """
    Awards tiny XP for a micro mission. Uses mission.xp_reward if set; otherwise MICRO_XP_DEFAULT.
    Optional: enforce a simple daily cap by summing awarded micro XP in today's completed micro assignments.
    """
    xp = int(mission.xp_reward or MICRO_XP_DEFAULT)

    # Optional daily cap enforcement (simple approach via query)
    try:
        today = date.today().isoformat()
        # Sum XP from completed micro missions today
        today_completed_micro = db.query(MissionAssignment).join(Mission).filter(
            MissionAssignment.user_id == user_id,
            MissionAssignment.date == today,
            MissionAssignment.status == "completed",
            Mission.type == "micro"
        ).all()
        total_awarded_today = 0
        for a in today_completed_micro:
            m = db.query(Mission).filter(Mission.id == a.mission_id).first()
            if m and m.xp_reward:
                total_awarded_today += int(m.xp_reward)
        if MICRO_DAILY_CAP and (total_awarded_today + xp) > MICRO_DAILY_CAP:
            # clamp to cap remainder
            xp = max(0, MICRO_DAILY_CAP - total_awarded_today)
    except Exception:
        # If any problem occurs, do not block; proceed with default tiny XP
        pass

    if xp > 0:
        from .stats import add_xp
        # Map micro to a neutral stat (keep consistent with existing default).
        # Your complete_mission already defaults to "Proficiency" for unknown types.
        add_xp(user_id, "Proficiency", xp, db)


def mark_micro_completed(assignment_id: int, db: Session) -> dict:
    """
    Transactionally mark a MICRO mission assignment as completed, with bedtime safety gates.
    Returns: {"ok": bool, "errors": [..]} and includes small XP award.
    """
    assign = db.query(MissionAssignment).filter(MissionAssignment.id == assignment_id).first()
    if not assign:
        return {"ok": False, "errors": ["Assignment not found."]}

    if assign.status == "completed":
        return {"ok": True, "errors": []}  # already done; idempotent

    mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
    if not mission:
        return {"ok": False, "errors": ["Mission not found."]}

    if (mission.type or "").lower() != "micro":
        return {"ok": False, "errors": ["Assignment is not a micro mission."]}

    # Compute time context for bedtime gate
    time_context = compute_time_context(assign.user_id, db)
    ok, reason = can_mark_micro_now(assign, time_context, db)
    if not ok:
        return {"ok": False, "errors": [reason]}

    # Perform transactional update
    try:
        assign.status = "completed"
        assign.completed_at = datetime.now()

        # Award tiny XP
        award_micro_xp(assign.user_id, mission, db)

        # Audit (if model exists as in your imports)
        try:
            audit = AuditLog(
                user_id=assign.user_id,
                event_type="mission_micro_completed",
                meta_json={
                    "mission_id": mission.id,
                    "assignment_id": assign.id,
                    "date": assign.date,
                    "time_context": time_context,
                    "awarded_xp": int(mission.xp_reward or MICRO_XP_DEFAULT),
                }
            )
            db.add(audit)
        except Exception:
            # If AuditLog schema differs, don't block completion
            pass

        db.commit()
        return {"ok": True, "errors": []}
    except Exception as e:
        db.rollback()
        return {"ok": False, "errors": [str(e)]}


def get_todays_micro_assignments(user_id: int, db: Session):
    today = date.today().isoformat()
    return db.query(MissionAssignment).join(Mission).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == today,
        MissionAssignment.status == "pending",
        Mission.type == "micro"
    ).all()


def _is_micro_type(mtype: str, duration_minutes: int) -> bool:
    m = (mtype or "").lower()
    return m == "micro" or (duration_minutes is not None and int(duration_minutes) <= 5)


def compute_time_context(user_id: int, db: Session) -> dict:
    """
    Compute time context for the user based on their day_end_time_local (UTC assumed).

    Returns:
        {
            "now_local": datetime str,
            "bedtime_cutoff_local": datetime str,
            "midnight_local": datetime str,
            "mins_to_bedtime": int,
            "mins_to_midnight": int,
            "effective_mins_to_bedtime": int,
            "effective_mins_to_midnight": int,
            "buffer_minutes": int
        }
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()

    # Get day end time (stored as HH:MM string)
    day_end_str = profile.day_end_time_local if profile else "21:30"
    try:
        day_end_h, day_end_m = map(int, day_end_str.split(":"))
    except Exception:
        day_end_h, day_end_m = 21, 30

    # Compute times (using local datetime without timezone library)
    now_local = datetime.now()
    bedtime_cutoff_local = now_local.replace(hour=day_end_h, minute=day_end_m, second=0, microsecond=0)
    midnight_local = now_local.replace(hour=23, minute=59, second=59, microsecond=0)

    buffer_minutes = 15

    mins_to_bedtime = max(0, int((bedtime_cutoff_local - now_local).total_seconds() / 60))
    mins_to_midnight = max(0, int((midnight_local - now_local).total_seconds() / 60))

    effective_mins_to_bedtime = max(0, mins_to_bedtime - buffer_minutes)
    effective_mins_to_midnight = max(0, mins_to_midnight - buffer_minutes)

    return {
        "now_local": now_local.isoformat(),
        "bedtime_cutoff_local": bedtime_cutoff_local.isoformat(),
        "midnight_local": midnight_local.isoformat(),
        "mins_to_bedtime": mins_to_bedtime,
        "mins_to_midnight": mins_to_midnight,
        "effective_mins_to_bedtime": effective_mins_to_bedtime,
        "effective_mins_to_midnight": effective_mins_to_midnight,
        "buffer_minutes": buffer_minutes
    }


def build_planner_context(user_id: int, date_str: str, minutes_cap: int, db: Session,
                          journal_signals_json: dict = None, voice_intent_summary: str = None) -> dict:
    """
    Build full context for AI planner.

    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        minutes_cap: Max total minutes for the day
        db: Database session
        journal_signals_json: Optional journal signals
        voice_intent_summary: Optional voice intent

    Returns:
        Context dict for Gemini prompt
    """
    user = db.query(User).filter(User.id == user_id).first()
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()

    time_context = compute_time_context(user_id, db)

    # Get streak and last 7 days completions
    today_date = date.fromisoformat(date_str)
    week_ago = today_date - timedelta(days=7)

    last_7_assignments = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date >= week_ago.isoformat(),
        MissionAssignment.status == "completed"
    ).count()

    streak = profile.streak_count if profile else 0

    # Build context
    context = {
        "user_handle": user.handle if user else "Student",
        "goals_json": profile.goals_json if profile else {},
        "streak_count": streak,
        "last_7_days_completed": last_7_assignments,
        "minutes_cap": minutes_cap,
        "time_context": time_context,
        "journal_signals": journal_signals_json or {},
        "voice_intent": voice_intent_summary or ""
    }

    return context


def generate_ai_plan_json(context: dict) -> dict:
    """
    Call Gemini to generate daily plan JSON.

    Args:
        context: Output from build_planner_context

    Returns:
        Parsed plan JSON (or empty dict if failed)
    """
    time_ctx = context.get("time_context", {})
    after_bedtime = time_ctx.get("effective_mins_to_bedtime", 0) == 0

    # Use a template with escaped braces and format to avoid f-string brace parsing issues
    prompt_template = """You are a student life RPG mission planner. Generate a JSON plan for today.

User: {user_handle}
Current Streak: {streak_count} days
Last 7 days completed: {last7} missions
Minutes available today: {minutes_cap}

Time context:
- Time to bedtime cutoff: {mins_bed} mins
- Time to midnight: {mins_mid} mins
- After bedtime cutoff: {after_bedtime}

Journal signals (if any): {journal_signals}
Voice intent (if any): {voice_intent}

STRICT RULES:
1. Generate 5-7 missions
2. Types ONLY: study, fitness, sleep, nutrition, reflection, social, chores
3. Difficulties: easy, medium, hard
4. Duration: 5-60 minutes each
5. XP: 5-60 per mission
6. Total duration <= {minutes_cap} minutes
7. Include at least one micro mission (<=5 mins)
8. Each mission needs stat_targets array
9. NO profanity or adult content

AFTER BEDTIME ({after_bedtime}):
- If true: ONLY reflection/sleep missions allowed
- If true: ALL must be easy difficulty
- If true: ALL must be <=15 minutes
- If true: Prefer micro missions

Return ONLY valid JSON, no markdown:
{{
  "date": "YYYY-MM-DD",
  "timezone": "Area/City",
  "missions": [
    {{
      "title": "mission title",
      "type": "study|fitness|sleep|nutrition|reflection|social|chores",
      "difficulty": "easy|medium|hard",
      "duration_minutes": 5-60,
      "xp_reward": 5-60,
      "stat_targets": ["knowledge", "guts", "proficiency", "kindness", "charm"],
      "micro": {{"title": "short title", "duration_minutes": 1-5, "xp_reward": 3-15}},
      "why_this": "one sentence why"
    }}
  ],
  "notes": "brief note"
}}"""
    prompt = prompt_template.format(
        user_handle=context.get('user_handle'),
        streak_count=context.get('streak_count'),
        last7=context.get('last_7_days_completed'),
        minutes_cap=context.get('minutes_cap'),
        mins_bed=time_ctx.get('effective_mins_to_bedtime', 0),
        mins_mid=time_ctx.get('effective_mins_to_midnight', 0),
        after_bedtime=after_bedtime,
        journal_signals=json.dumps(context.get('journal_signals', {})),
        voice_intent=context.get('voice_intent', ''),
    )

    return call_gemini_json(prompt, temperature=0.3, max_tokens=900)


def validate_plan(plan_json: dict, minutes_cap: int, time_context: dict) -> tuple:
    """
    Validate plan JSON against rules.

    Returns:
        (is_valid, error_list)
    """
    errors = []

    if not plan_json or "missions" not in plan_json:
        errors.append("Invalid plan JSON structure")
        return False, errors

    missions = plan_json.get("missions", [])

    # Check count
    if len(missions) < 5 or len(missions) > 7:
        errors.append(f"Must have 5-7 missions, got {len(missions)}")

    # Check types, duration, xp, duplicates
    titles = set()
    total_duration = 0
    has_micro = False

    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0

    for i, mission in enumerate(missions):
        title = mission.get("title", "")
        mission_type = mission.get("type", "")
        difficulty = mission.get("difficulty", "")
        duration = mission.get("duration_minutes", 0)
        xp = mission.get("xp_reward", 0)

        # Type check
        if mission_type not in ALLOWED_MISSION_TYPES:
            errors.append(f"Mission {i}: invalid type '{mission_type}'")

        # After bedtime rules
        if after_bedtime:
            if mission_type not in WIND_DOWN_TYPES:
                errors.append(f"Mission {i}: after bedtime, only reflection/sleep allowed, got '{mission_type}'")
            if difficulty != "easy":
                errors.append(f"Mission {i}: after bedtime, must be easy difficulty")
            if duration > 15:
                errors.append(f"Mission {i}: after bedtime, max 15 minutes, got {duration}")

        # Duration and XP
        if duration < 5 or duration > 60:
            errors.append(f"Mission {i}: duration {duration} not in 5-60 range")

        if xp < 5 or xp > 60:
            errors.append(f"Mission {i}: xp {xp} not in 5-60 range")

        # Micro check
        micro = mission.get("micro", {})
        if micro and micro.get("duration_minutes", 0) <= 5:
            has_micro = True

        # Duplicates
        if title in titles:
            errors.append(f"Mission {i}: duplicate title '{title}'")
        titles.add(title)

        # Unsafe keywords
        if any(kw in title.lower() for kw in UNSAFE_KEYWORDS):
            errors.append(f"Mission {i}: unsafe content in title")

        total_duration += duration

    # Total duration
    if total_duration > minutes_cap:
        errors.append(f"Total duration {total_duration} exceeds cap {minutes_cap}")

    if not has_micro:
        errors.append("Must include at least one micro mission (<=5 mins)")

    return len(errors) == 0, errors


def preview_plan(user_id: int, date_str: str, source: str, plan_json: dict, time_context: dict,
                 minutes_cap: int, db: Session) -> tuple:
    """
    Create a PlanRun with status=previewed.

    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        source: "missions_page", "journal", or "voice"
        plan_json: Validated plan JSON
        time_context: Time context dict
        minutes_cap: Minutes cap
        db: Database session

    Returns:
        (PlanRun object, plan_json)
    """
    # Check if already have assigned plan for today
    existing_assigned = db.query(PlanRun).filter(
        PlanRun.user_id == user_id,
        PlanRun.date == date_str,
        PlanRun.kind == "full_plan",
        PlanRun.status == "assigned"
    ).first()

    plan_version = 1
    if existing_assigned:
        plan_version = existing_assigned.plan_version + 1

    plan_run = PlanRun(
        user_id=user_id,
        date=date_str,
        plan_version=plan_version,
        source=source,
        kind="full_plan",
        status="previewed",
        meta_json={
            "minutes_cap": minutes_cap,
            "time_context": time_context,
            "plan_json": plan_json
        }
    )

    db.add(plan_run)
    db.commit()
    db.refresh(plan_run)

    return plan_run, plan_json


def assign_plan_creating_daily_missions(user_id: int, date_str: str, plan_run: PlanRun, db: Session) -> bool:
    """
    Assign plan: create NEW Mission rows + MissionAssignments.
    Also creates separate MICRO mission+assignment when mission_data contains a 'micro' object.

    Idempotency:
      - If plan_run already assigned, return False.
      - Supersedes older assigned plans for the same day (archives pending assignments).
    """
    # Check if already assigned today (existing behavior)
    existing_assigned = db.query(PlanRun).filter(
        PlanRun.user_id == user_id,
        PlanRun.date == date_str,
        PlanRun.kind == "full_plan",
        PlanRun.status == "assigned"
    ).all()

    # If this plan_run is already assigned, skip
    if plan_run.status == "assigned":
        return False

    # Supersede earlier assigned plans (archive their pending assignments)
    for old_plan in existing_assigned:
        if old_plan.id != plan_run.id:
            old_plan.status = "superseded"
            old_assigns = db.query(MissionAssignment).filter(
                MissionAssignment.user_id == user_id,
                MissionAssignment.date == date_str,
                MissionAssignment.plan_run_id == old_plan.id,
                MissionAssignment.status == "pending"
            ).all()
            for a in old_assigns:
                a.status = "archived"

    # Create missions from plan_json
    plan_json = (plan_run.meta_json or {}).get("plan_json", {})
    missions_data = plan_json.get("missions", []) or []

    # Helper: normalize micro minutes/xp safely
    def _safe_int(x, default):
        try:
            return int(x)
        except Exception:
            return default

    created_count = 0
    created_micro_count = 0

    for mission_data in missions_data:
        # 1) Create MAIN mission
        mission = Mission(
            title=mission_data.get("title", "") or "",
            type=mission_data.get("type", "") or "",
            difficulty=mission_data.get("difficulty", "easy") or "easy",
            xp_reward=_safe_int(mission_data.get("xp_reward", 10), 10),
            duration_minutes=_safe_int(mission_data.get("duration_minutes", 30), 30),
            created_for_date=date_str,
            created_by_system=True,
        )

        # Store why + micro metadata on the MAIN mission for transparency
        micro_obj = mission_data.get("micro", {}) or {}
        why_this = mission_data.get("why_this", "") or ""
        mission.geo_rule_json = {
            "why": why_this,
            "micro_title": micro_obj.get("title", "") or "",
            "micro_duration_minutes": _safe_int(micro_obj.get("duration_minutes", 0), 0),
            "micro_xp_reward": _safe_int(micro_obj.get("xp_reward", 0), 0),
        }

        db.add(mission)
        db.flush()  # get mission.id without committing

        # 2) Create MAIN assignment
        assign = MissionAssignment(
            user_id=user_id,
            mission_id=mission.id,
            date=date_str,
            status="pending",
            plan_run_id=plan_run.id,
        )
        # Optional but nice: proof_json marker
        if hasattr(assign, "proof_json"):
            assign.proof_json = {"source": "plan_main", "plan_run_id": plan_run.id}

        db.add(assign)

        created_count += 1

        # 3) Create MICRO mission + assignment (NEW FEATURE B core)
        if micro_obj and (micro_obj.get("title") or "").strip():
            micro_minutes = _safe_int(micro_obj.get("duration_minutes", 3), 3)
            micro_xp = _safe_int(micro_obj.get("xp_reward", 5), 5)

            micro_mission = Mission(
                title=f"\U0001F7A3 {micro_obj.get('title','').strip()}",
                type="micro",
                difficulty="easy",
                xp_reward=micro_xp,
                duration_minutes=micro_minutes,
                created_for_date=date_str,
                created_by_system=True,
            )

            micro_why = micro_obj.get("why_this", "") or ""
            micro_mission.geo_rule_json = {
                "why": micro_why,
                "kind": "micro",
                "parent_mission_id": mission.id,
                "parent_title": mission.title,
                "parent_type": mission.type,  # REQUIRED for bedtime gate
                "from_plan_run_id": plan_run.id,
            }

            db.add(micro_mission)
            db.flush()

            micro_assign = MissionAssignment(
                user_id=user_id,
                mission_id=micro_mission.id,
                date=date_str,
                status="pending",
                plan_run_id=plan_run.id,
            )
            if hasattr(micro_assign, "proof_json"):
                micro_assign.proof_json = {
                    "source": "plan_micro",
                    "parent_mission_id": mission.id,
                    "parent_title": mission.title,
                    "plan_run_id": plan_run.id,
                }

            db.add(micro_assign)
            created_micro_count += 1

    # Mark plan_run assigned
    plan_run.status = "assigned"

    # Commit once
    db.commit()

    # Optional: store counts for debugging/audit visibility
    try:
        meta = plan_run.meta_json or {}
        meta["created_missions_count"] = created_count
        meta["created_micro_missions_count"] = created_micro_count
        plan_run.meta_json = meta
        db.commit()
    except Exception:
        # no need to fail assignment if meta_json update fails
        db.rollback()

    return True


# Existing functions

def generate_daily_missions(user_id: int, journal_metrics: dict, db: Session):
    """Legacy function - kept for backward compatibility."""
    today = date.today().isoformat()
    existing = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == today
    ).count()
    if existing > 0:
        return

    missions = []

    sleep = float(journal_metrics.get("sleep_hours", 0) or 0)
    if sleep < 7:
        missions.append({
            "title": "Power Nap or Early Bedtime",
            "type": "sleep",
            "xp_reward": 20,
            "geo_rule_json": {"why": "You slept less than 7 hours."}
        })

    study = int(journal_metrics.get("study_minutes", 0) or 0)
    if study < 30:
        missions.append({
            "title": "Focus Session: 25 mins",
            "type": "study",
            "xp_reward": 30,
            "geo_rule_json": {"why": "Daily study goal not met."}
        })

    missions.append({
        "title": "Evening Reflection",
        "type": "reflection",
        "xp_reward": 15,
        "geo_rule_json": {"why": "Daily mindfulness."}
    })

    move = int(journal_metrics.get("movement_minutes", 0) or 0)
    if move < 15:
        missions.append({
            "title": "Quick Walk or Stretch",
            "type": "fitness",
            "xp_reward": 20,
            "geo_rule_json": {"why": "Movement goal not met."}
        })

    for m_data in missions:
        mission = Mission(
            title=m_data["title"],
            type=m_data["type"],
            xp_reward=m_data["xp_reward"],
            created_for_date=today,
            geo_rule_json=m_data["geo_rule_json"]
        )
        db.add(mission)
        db.commit()
        db.refresh(mission)

        assign = MissionAssignment(
            user_id=user_id,
            mission_id=mission.id,
            date=today,
            status="pending"
        )
        db.add(assign)
    db.commit()


def get_todays_missions(user_id: int, db: Session):
    """Get all missions assigned for today."""
    today = date.today().isoformat()
    return db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == today
    ).all()


def complete_mission(assignment_id: int, db: Session):
    """Complete a mission assignment."""
    assign = db.query(MissionAssignment).filter(MissionAssignment.id == assignment_id).first()
    if assign and assign.status != "completed":
        assign.status = "completed"
        assign.completed_at = datetime.now()
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        if mission:
            from .stats import add_xp
            stat_map = {
                "study": "Knowledge",
                "fitness": "Guts",
                "reflection": "Proficiency",
                "sleep": "Kindness",
                "nutrition": "Charm",
                "social": "Charm",
                "chores": "Guts",
                "micro": "Proficiency",  # explicit mapping for micro
            }
            stat_type = stat_map.get(mission.type, "Proficiency")
            add_xp(assign.user_id, stat_type, mission.xp_reward, db)
        db.commit()


# Swap proposal functions (Step 3C)

def get_pending_missions(user_id: int, date_str: str, db: Session) -> list:
    """
    Get all pending missions for a given date.

    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        db: Database session

    Returns:
        List of dicts with {title, type, duration_minutes, xp_reward}
    """
    assignments = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == date_str,
        MissionAssignment.status == "pending"
    ).all()

    pending = []
    for assign in assignments:
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        if mission:
            if (mission.type or "").lower() == "micro":
                continue  # skip micros for swap proposals
            pending.append({
                "title": mission.title,
                "type": mission.type,
                "duration_minutes": mission.duration_minutes or 30,
                "xp_reward": mission.xp_reward or 10
            })

    return pending


def propose_swaps(
    user_id: int,
    date_str: str,
    minutes_cap: int,
    db: Session,
    journal_signals_json: dict = None,
    voice_intent_summary: dict = None
) -> dict:
    """
    Propose swaps for pending missions using Gemini.

    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        minutes_cap: Daily minutes cap
        db: Database session
        journal_signals_json: Optional journal signals dict
        voice_intent_summary: Optional voice intent dict

    Returns:
        Swap JSON dict with schema:
        {
          "date": "YYYY-MM-DD",
          "swap_count": 0-3,
          "no_swap_reason": "short if 0",
          "replacements": [{"replace_title": "...", "new_mission": {...}, "reason": "..."}],
          "notes": "..."
        }
    """
    # Get pending missions
    pending_missions = get_pending_missions(user_id, date_str, db)

    if not pending_missions:
        return {
            "date": date_str,
            "swap_count": 0,
            "no_swap_reason": "No pending missions to swap.",
            "replacements": [],
            "notes": ""
        }

    # Compute time context
    time_context = compute_time_context(user_id, db)

    # Determine if after bedtime cutoff
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    effective_mins = time_context.get("effective_mins_to_midnight" if after_bedtime else "effective_mins_to_bedtime", 0)

    # Calculate dynamic swap_limit based on remaining time
    if effective_mins < 15:
        swap_limit = 1
    elif effective_mins < 30:
        swap_limit = 2
    else:
        swap_limit = 3

    # Build pending missions list for prompt
    pending_str = "\n".join([f"- {m['title']} ({m['type']}, {m['duration_minutes']} mins, +{m['xp_reward']} XP)" for m in pending_missions])

    # Build constraints string
    if after_bedtime:
        time_constraint = f"After bedtime cutoff. Only reflection/sleep allowed, easy difficulty, max 15 mins per mission. Time left: {effective_mins} mins (to midnight)."
    else:
        time_constraint = f"Before bedtime cutoff. Any mission type allowed. Time left: {effective_mins} mins (to bedtime), then {time_context.get('effective_mins_to_midnight', 0)} mins to midnight."

    # Build signals summary
    signals_str = ""
    if journal_signals_json:
        mood = journal_signals_json.get("mood", "")
        energy = journal_signals_json.get("energy", 3)
        stress = journal_signals_json.get("stress", 2)
        signals_str = f"\nJournal signals: mood={mood}, energy={energy}/5, stress={stress}/5. Wins: {journal_signals_json.get('wins', [])}. Needs: {journal_signals_json.get('needs', [])}."

    if voice_intent_summary:
        intent = voice_intent_summary.get("intent_summary", "")
        priority = voice_intent_summary.get("priority", "")
        signals_str += f"\nVoice intent: {intent}. Priority: {priority}."

    # Use a template with escaped braces and format to avoid f-string brace parsing issues
    prompt_template = """You are a mission swap assistant. Propose up to {swap_limit} swaps to improve the user's day.

Pending missions:
{pending_str}

Time context:
{time_constraint}
{signals_str}

Rules:
1. Only swap pending missions (not completed ones).
2. Each swap replaces one pending mission with a NEW mission of same/similar type.
3. Total replacements duration must fit available time.
4. If after bedtime: ONLY reflection/sleep, easy difficulty, max 15 mins each.
5. Each replacement needs a "reason" (1-2 sentences why this swap helps).
6. If you can't improve the day, return swap_count=0 with a short no_swap_reason.

Return ONLY valid JSON, no markdown:
{{
  "date": "{date_str}",
  "swap_count": 0-{swap_limit},
  "no_swap_reason": "short if swap_count=0, empty otherwise",
  "replacements": [
    {{
      "replace_title": "exact title of pending mission to replace",
      "new_mission": {{
        "title": "new mission title",
        "type": "study|fitness|sleep|nutrition|reflection|social|chores",
        "difficulty": "easy|medium|hard",
        "duration_minutes": 5-60,
        "xp_reward": 5-60,
        "stat_targets": ["stat1", "stat2"],
        "micro": {{"title": "micro title", "duration_minutes": 1-5, "xp_reward": 3-15}},
        "why_this": "one sentence why"
      }},
      "reason": "1-2 sentence reason for swap"
    }}
  ],
  "notes": "brief note"
}}"""
    prompt = prompt_template.format(
        swap_limit=swap_limit,
        pending_str=pending_str,
        time_constraint=time_constraint,
        signals_str=signals_str,
        date_str=date_str,
    )

    # Call Gemini
    swap_json = call_gemini_json(prompt, temperature=0.25, max_tokens=700)

    if not swap_json:
        # Fallback: no swaps
        return {
            "date": date_str,
            "swap_count": 0,
            "no_swap_reason": "AI swap assistant unavailable.",
            "replacements": [],
            "notes": ""
        }

    # Ensure required keys exist
    if "swap_count" not in swap_json:
        swap_json["swap_count"] = 0
    if "replacements" not in swap_json:
        swap_json["replacements"] = []
    if "no_swap_reason" not in swap_json:
        swap_json["no_swap_reason"] = ""
    if "notes" not in swap_json:
        swap_json["notes"] = ""

    # Enforce swap_count <= swap_limit
    swap_json["swap_count"] = min(swap_json.get("swap_count", 0), swap_limit)

    return swap_json


def validate_swap_plan(swap_json: dict, pending_missions: list, time_context: dict) -> tuple:
    """
    Validate swap JSON against all rules.

    Args:
        swap_json: Output from propose_swaps()
        pending_missions: List of pending missions (from get_pending_missions())
        time_context: Output from compute_time_context()

    Returns:
        (is_valid, error_list)
    """
    errors = []

    # Validate swap_json structure
    if not swap_json or "swap_count" not in swap_json:
        errors.append("Invalid swap JSON: missing swap_count")
        return False, errors

    swap_count = swap_json.get("swap_count", 0)
    replacements = swap_json.get("replacements", [])
    no_swap_reason = swap_json.get("no_swap_reason", "")

    # Calculate swap_limit from time_context
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    effective_mins = time_context.get("effective_mins_to_midnight" if after_bedtime else "effective_mins_to_bedtime", 0)

    if effective_mins < 15:
        swap_limit = 1
    elif effective_mins < 30:
        swap_limit = 2
    else:
        swap_limit = 3

    # Validate swap_count
    if swap_count < 0 or swap_count > 3:
        errors.append(f"swap_count must be 0-3, got {swap_count}")

    if swap_count > swap_limit:
        errors.append(f"swap_count {swap_count} exceeds time-based limit {swap_limit}")

    # Validate swap_count == 0 -> replacements empty and no_swap_reason present
    if swap_count == 0:
        if replacements:
            errors.append("If swap_count==0, replacements must be empty")
        if not no_swap_reason:
            errors.append("If swap_count==0, no_swap_reason must be present")
        # If swap_count=0, we're done
        return len(errors) == 0, errors

    # Validate swap_count > 0 -> replacements must match
    if len(replacements) != swap_count:
        errors.append(f"swap_count={swap_count} but got {len(replacements)} replacements")

    # Get list of pending mission titles
    pending_titles = [m["title"] for m in pending_missions]
    replaced_titles = set()

    total_duration = 0

    for i, repl in enumerate(replacements):
        replace_title = repl.get("replace_title", "")
        new_mission = repl.get("new_mission", {})

        # Check replace_title exists
        if replace_title not in pending_titles:
            errors.append(f"Replacement {i}: replace_title '{replace_title}' not found in pending missions")

        # Check for duplicates
        if replace_title in replaced_titles:
            errors.append(f"Replacement {i}: duplicate replace_title '{replace_title}'")
        replaced_titles.add(replace_title)

        # Validate new_mission
        m_type = new_mission.get("type", "")
        m_difficulty = new_mission.get("difficulty", "")
        m_duration = new_mission.get("duration_minutes", 0)
        m_xp = new_mission.get("xp_reward", 0)
        micro = new_mission.get("micro", {})
        title = new_mission.get("title", "")

        # Type check
        if m_type not in ALLOWED_MISSION_TYPES:
            errors.append(f"Replacement {i}: invalid type '{m_type}'")

        # After bedtime rules
        if after_bedtime:
            if m_type not in WIND_DOWN_TYPES:
                errors.append(f"Replacement {i}: after bedtime, only reflection/sleep allowed, got '{m_type}'")
            if m_difficulty != "easy":
                errors.append(f"Replacement {i}: after bedtime, must be easy difficulty")
            if m_duration > 15:
                errors.append(f"Replacement {i}: after bedtime, max 15 minutes, got {m_duration}")

        # Duration and XP ranges
        if m_duration < 5 or m_duration > 60:
            errors.append(f"Replacement {i}: duration {m_duration} not in 5-60 range")

        if m_xp < 5 or m_xp > 60:
            errors.append(f"Replacement {i}: xp {m_xp} not in 5-60 range")

        # Micro required and duration <= 5
        if not micro or "title" not in micro:
            errors.append(f"Replacement {i}: micro mission required")
        elif micro.get("duration_minutes", 0) > 5:
            errors.append(f"Replacement {i}: micro duration must be <= 5 mins")

        # Unsafe keywords
        if any(kw in title.lower() for kw in UNSAFE_KEYWORDS):
            errors.append(f"Replacement {i}: unsafe content in title")

        total_duration += m_duration

    # Time constraint check
    if after_bedtime:
        time_limit = time_context.get("effective_mins_to_midnight", 0)
        if total_duration > time_limit:
            errors.append(f"After bedtime: total replacement duration {total_duration} exceeds midnight limit {time_limit} mins")
    else:
        time_limit = time_context.get("effective_mins_to_bedtime", 0)
        if total_duration > time_limit:
            errors.append(f"Before bedtime: total replacement duration {total_duration} exceeds bedtime limit {time_limit} mins")

    return len(errors) == 0, errors


def apply_swaps(user_id: int, date_str: str, swap_json: dict, db: Session, source: str = "missions_page") -> PlanRun:
    """
    Apply validated swaps: archive old pending assignments, create new missions and assignments.

    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        swap_json: Validated swap JSON (should pass validate_swap_plan first)
        db: Database session
        source: Origin ("missions_page", "journal", or "voice")

    Returns:
        PlanRun object with kind="swap", status="assigned"
    """
    # Get pending missions and time context for meta_json
    pending_missions = get_pending_missions(user_id, date_str, db)
    time_context = compute_time_context(user_id, db)

    # Calculate swap_limit
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    effective_mins = time_context.get("effective_mins_to_midnight" if after_bedtime else "effective_mins_to_bedtime", 0)

    if effective_mins < 15:
        swap_limit = 1
    elif effective_mins < 30:
        swap_limit = 2
    else:
        swap_limit = 3

    swap_count = swap_json.get("swap_count", 0)
    replacements = swap_json.get("replacements", [])

    # Create PlanRun for this swap batch
    plan_run = PlanRun(
        user_id=user_id,
        date=date_str,
        plan_version=1,
        source=source,
        kind="swap",
        status="assigned",
        meta_json={
            "time_context": time_context,
            "swap_limit": swap_limit,
            "swap_count": swap_count,
            "swap_json": swap_json
        }
    )
    db.add(plan_run)
    db.commit()
    db.refresh(plan_run)

    # Process replacements
    for swap_index, repl in enumerate(replacements):
        replace_title = repl.get("replace_title", "")
        new_mission_data = repl.get("new_mission", {})

        # Find and archive the pending assignment
        old_assign = db.query(MissionAssignment).filter(
            MissionAssignment.user_id == user_id,
            MissionAssignment.date == date_str,
            MissionAssignment.status == "pending"
        ).join(Mission).filter(Mission.title == replace_title).first()

        if old_assign:
            old_assign.status = "archived"
            if old_assign.proof_json is None:
                old_assign.proof_json = {}
            old_assign.proof_json["swapped_out"] = True
            old_assign.proof_json["swap_plan_run_id"] = plan_run.id

        # Create new mission
        new_mission = Mission(
            title=new_mission_data.get("title", ""),
            type=new_mission_data.get("type", ""),
            difficulty=new_mission_data.get("difficulty", "easy"),
            xp_reward=new_mission_data.get("xp_reward", 10),
            duration_minutes=new_mission_data.get("duration_minutes", 30),
            created_for_date=date_str,
            created_by_system=True
        )

        # Store micro and why_this in geo_rule_json
        micro = new_mission_data.get("micro", {})
        why_this = new_mission_data.get("why_this", "")
        reason = repl.get("reason", "")

        new_mission.geo_rule_json = {
            "why": why_this,
            "swap_reason": reason,
            "micro_title": micro.get("title", ""),
            "micro_duration_minutes": micro.get("duration_minutes", 0),
            "micro_xp_reward": micro.get("xp_reward", 0),
            "swap_index": swap_index
        }

        db.add(new_mission)
        db.commit()
        db.refresh(new_mission)

        # Create assignment linked to swap PlanRun
        new_assign = MissionAssignment(
            user_id=user_id,
            mission_id=new_mission.id,
            date=date_str,
            status="pending",
            plan_run_id=plan_run.id
        )
        db.add(new_assign)

    db.commit()

    # Log to AuditLog if available
    try:
        audit = AuditLog(
            user_id=user_id,
            event_type="missions_swapped",
            meta_json={
                "date": date_str,
                "swap_count": swap_count,
                "swap_limit": swap_limit,
                "source": source,
                "plan_run_id": plan_run.id
            }
        )
        db.add(audit)
        db.commit()
    except Exception:
        # AuditLog may not exist, silently pass
        pass

    return plan_run


def get_nims_time_context(profile=None, now=None) -> dict:
    """
    Returns time context for NIMS response shaping.

    This helper does not modify plans or missions.
    It only exposes safe timing metadata.
    """

    default_context = {
        "after_day_end": False,
        "recommended_response_length": "short",
        "recommended_cognitive_load": "low",
        "source": "nims_default_time_context",
    }

    try:
        if "compute_time_context" in globals():
            computed = compute_time_context(profile=profile, now=now)

            if isinstance(computed, dict):
                return {
                    "after_day_end": bool(computed.get("after_day_end", False)),
                    "recommended_response_length": computed.get(
                        "recommended_response_length",
                        "short",
                    ),
                    "recommended_cognitive_load": computed.get(
                        "recommended_cognitive_load",
                        "low",
                    ),
                    "source": "missions.compute_time_context",
                }

    except TypeError:
        try:
            computed = compute_time_context(profile, now)

            if isinstance(computed, dict):
                return {
                    "after_day_end": bool(computed.get("after_day_end", False)),
                    "recommended_response_length": computed.get(
                        "recommended_response_length",
                        "short",
                    ),
                    "recommended_cognitive_load": computed.get(
                        "recommended_cognitive_load",
                        "low",
                    ),
                    "source": "missions.compute_time_context",
                }
        except Exception:
            pass

    except Exception:
        pass

    return default_context

