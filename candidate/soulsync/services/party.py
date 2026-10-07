# soulsync/services/party.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import Profile, PlanRun, Mission, MissionAssignment, AuditLog, User
from .missions import compute_time_context

# Allowed mission types from your stack
ALLOWED_MISSION_TYPES = ["study", "fitness", "sleep", "nutrition", "reflection", "social", "chores"]

# Default party roster (stored under Profile.goals_json["party_roster"])
DEFAULT_ROSTER = [
    {"name": "Kai", "role": "Scout", "traits": ["active", "outdoors"], "emoji": "🧭"},
    {"name": "Mira", "role": "Healer", "traits": ["calm", "care"], "emoji": "🪷"},
    {"name": "Arun", "role": "Mentor", "traits": ["focus", "study"], "emoji": "🧠"},
]


def _safe_int(x, default):
    try:
        return int(x)
    except Exception:
        return default


def _load_profile(user_id: int, db: Session) -> Optional[Profile]:
    return db.query(Profile).filter(Profile.user_id == user_id).first()


def get_or_create_party_roster(user_id: int, db: Session) -> List[Dict[str, Any]]:
    """
    Return party roster from Profile.goals_json['party_roster'], creating defaults if missing.
    """
    profile = _load_profile(user_id, db)
    if not profile:
        # Create ephemeral default roster if profile is missing
        return DEFAULT_ROSTER.copy()

    goals = profile.goals_json or {}
    roster = goals.get("party_roster")
    if not roster or not isinstance(roster, list):
        goals["party_roster"] = DEFAULT_ROSTER.copy()
        profile.goals_json = goals
        try:
            db.add(profile)
            db.commit()
        except Exception:
            db.rollback()
        roster = goals["party_roster"]
    return roster


def propose_party_missions(
    user_id: int,
    date_str: str,
    db: Session,
    *,
    journal_signals: Optional[Dict[str, Any]] = None,
    voice_intent: Optional[Dict[str, Any]] = None,
    time_context: Optional[Dict[str, Any]] = None,
    max_count: int = 2,
) -> Dict[str, Any]:
    """
    Deterministically propose up to `max_count` party missions (MVP, no Gemini).
    Respects after-bedtime wind-down rules (reflection/sleep only, easy, ≤15 min).
    Returns:
      {
        "date": str,
        "count": int,
        "replacements": [ { "member": {...}, "mission": {...}, "reason": str } ],
        "notes": str
      }
    """
    tc = time_context or compute_time_context(user_id, db)
    after_bedtime = tc.get("effective_mins_to_bedtime", 0) == 0
    roster = get_or_create_party_roster(user_id, db)

    s = journal_signals or {}
    mood = (s.get("mood") or "neutral").lower()
    energy = int(s.get("energy", 3) or 3)
    focus = int(s.get("focus", 3) or 3)
    stress = int(s.get("stress", 2) or 2)
    vi = voice_intent or {}
    priority = (vi.get("priority") or "other").lower()

    def mk_mission(member, title, mtype, minutes, xp, diff="easy", why=""):
        # Enforce after-bedtime rules
        if after_bedtime:
            mtype = "reflection" if mtype not in ("reflection", "sleep") else mtype
            minutes = min(minutes, 15)
            diff = "easy"
        return {
            "title": title,
            "type": mtype,
            "difficulty": diff,
            "duration_minutes": _safe_int(minutes, 10),
            "xp_reward": _safe_int(xp, 10),
            "stat_targets": ["proficiency", "kindness", "charm"],
            "why_this": why or f"{member['name']} ({member['role']}) suggests this for today.",
        }

    suggestions: List[Dict[str, Any]] = []
    for member in roster:
        role = (member.get("role") or "").lower()
        # Heuristic selection
        if after_bedtime:
            # Wind-down micros / short reflections or sleep setup
            if role in ("healer", "mentor"):
                suggestions.append({
                    "member": member,
                    "mission": mk_mission(member, "Evening reflection micro", "reflection", 5, 10,
                                          why="Gentle reflection to wind down."),
                    "reason": "Calm reflection fits wind‑down."
                })
            else:
                suggestions.append({
                    "member": member,
                    "mission": mk_mission(member, "Prepare sleep corner", "sleep", 10, 12,
                                          why="Set a soothing sleep routine."),
                    "reason": "Sleep setup helps end the day smoothly."
                })
        else:
            if role == "mentor" or priority == "study" or focus <= 3:
                suggestions.append({
                    "member": member,
                    "mission": mk_mission(member, "Focused study sprint", "study", 25, 25, diff="medium",
                                          why="A short sprint aligned to your intent."),
                    "reason": "Mentor supports focused time."
                })
            elif role == "scout" or energy >= 4:
                suggestions.append({
                    "member": member,
                    "mission": mk_mission(member, "Air & steps micro", "fitness", 10, 12,
                                          why="Move a little to refresh energy."),
                    "reason": "Scout favors a quick refresh outside."
                })
            elif role == "healer" or stress >= 3 or mood in ("sad", "low"):
                suggestions.append({
                    "member": member,
                    "mission": mk_mission(member, "Hydration + breathe", "nutrition", 8, 10,
                                          why="Water + breathe to ease stress."),
                    "reason": "Healer suggests small care actions."
                })
            else:
                suggestions.append({
                    "member": member,
                    "mission": mk_mission(member, "Desk tidy micro", "chores", 10, 10,
                                          why="Tiny tidy boosts focus."),
                    "reason": "A small tidy helps focus."
                })

        if len(suggestions) >= max_count:
            break

    if not suggestions:
        return {
            "date": date_str,
            "count": 0,
            "replacements": [],
            "notes": "No party suggestions at this time."
        }

    return {
        "date": date_str,
        "count": len(suggestions),
        "replacements": suggestions,
        "notes": "Party MVP deterministic suggestions."
    }


def preview_party_missions(
    user_id: int,
    date_str: str,
    party_json: Dict[str, Any],
    db: Session,
    source: str = "missions_page",
) -> PlanRun:
    """
    Create a PlanRun(kind='party', status='previewed') holding suggestions.
    """
    plan_run = PlanRun(
        user_id=user_id,
        date=date_str,
        plan_version=1,
        source=source,
        kind="party",
        status="previewed",
        meta_json={"party_json": party_json}
    )
    db.add(plan_run)
    db.commit()
    db.refresh(plan_run)
    return plan_run


def apply_party_missions(
    user_id: int,
    date_str: str,
    party_json: Dict[str, Any],
    db: Session,
    source: str = "missions_page",
) -> PlanRun:
    """
    Create Mission rows + MissionAssignments for suggested party missions.
    Creates PlanRun(kind='party', status='assigned').
    """
    plan_run = PlanRun(
        user_id=user_id,
        date=date_str,
        plan_version=1,
        source=source,
        kind="party",
        status="assigned",
        meta_json={"party_json": party_json}
    )
    db.add(plan_run)
    db.commit()
    db.refresh(plan_run)

    replacements = party_json.get("replacements", []) or []
    created_count = 0

    for idx, r in enumerate(replacements):
        member = r.get("member", {}) or {}
        m = r.get("mission", {}) or {}
        title = m.get("title", "") or ""
        mtype = m.get("type", "") or "reflection"

        # Sanity clamp to allowed types
        if mtype not in ALLOWED_MISSION_TYPES:
            mtype = "reflection"

        mission = Mission(
            title=f"🧑‍🤝‍🧑 {member.get('name','')} • {title}",
            type=mtype,
            difficulty=m.get("difficulty", "easy") or "easy",
            xp_reward=_safe_int(m.get("xp_reward", 10), 10),
            duration_minutes=_safe_int(m.get("duration_minutes", 10), 10),
            created_for_date=date_str,
            created_by_system=True,
        )
        mission.geo_rule_json = {
            "why": m.get("why_this", "") or r.get("reason", ""),
            "party_member": {
                "name": member.get("name"),
                "role": member.get("role"),
                "emoji": member.get("emoji"),
            },
            "party_index": idx,
            "from_plan_run_id": plan_run.id,
        }

        db.add(mission)
        db.commit()
        db.refresh(mission)

        assign = MissionAssignment(
            user_id=user_id,
            mission_id=mission.id,
            date=date_str,
            status="pending",
            plan_run_id=plan_run.id,
        )
        db.add(assign)
        db.commit()

        created_count += 1

    # Audit
    try:
        audit = AuditLog(
            user_id=user_id,
            event_type="party_missions_assigned",
            meta_json={"date": date_str, "count": created_count, "plan_run_id": plan_run.id}
        )
        db.add(audit)
        db.commit()
    except Exception:
        db.rollback()

    # Update meta counts
    try:
        meta = plan_run.meta_json or {}
        meta["created_party_missions_count"] = created_count
        plan_run.meta_json = meta
        db.commit()
    except Exception:
        db.rollback()

    return plan_run
