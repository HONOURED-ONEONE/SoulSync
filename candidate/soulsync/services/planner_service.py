from sqlalchemy.orm import Session
from ..models import MissionAssignment, Mission

def build_plan(user_id: int, date: str, minutes_cap: int, db: Session):
    """
    Build a time-blocking plan for the user.
    - Prioritizes recovery mission if exists
    - Ensures variety and total duration <= cap
    - Deterministic (no Gemini)
    """
    today_assigns = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == date
    ).all()
    
    planned = []
    total_minutes = 0
    
    # Prioritize recovery mission
    recovery_assign = [a for a in today_assigns if db.query(Mission).filter(Mission.id == a.mission_id).first().is_recovery]
    for a in recovery_assign:
        mission = db.query(Mission).filter(Mission.id == a.mission_id).first()
        duration = mission.duration_minutes or 10
        planned.append((a, mission, duration))
        total_minutes += duration
    
    # Add other missions by variety
    other_assigns = [a for a in today_assigns if a not in recovery_assign]
    type_counts = {}
    for a in other_assigns:
        mission = db.query(Mission).filter(Mission.id == a.mission_id).first()
        duration = mission.duration_minutes or 15
        if total_minutes + duration <= minutes_cap:
            type_counts[mission.type] = type_counts.get(mission.type, 0) + 1
            # Prioritize types we haven't done much
            if type_counts[mission.type] <= 2:
                planned.append((a, mission, duration))
                total_minutes += duration
    
    return planned

def apply_plan(user_id: int, date: str, mission_ids: list, db: Session):
    """Assign selected missions to a date (prevent duplicates)."""
    existing = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == date
    ).all()
    existing_mission_ids = set(a.mission_id for a in existing)
    
    for mid in mission_ids:
        if mid not in existing_mission_ids:
            assign = MissionAssignment(user_id=user_id, mission_id=mid, date=date, status="pending")
            db.add(assign)
    db.commit()
