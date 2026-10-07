from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import Profile, Mission, MissionAssignment

def check_and_handle_streak_break(user_id: int, db: Session):
    """
    Check if streak is broken (no completed mission today).
    If broken and shields available, create a recovery mission.
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return False
    
    today = datetime.now().strftime("%Y-%m-%d")
    completed_today = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == today,
        MissionAssignment.status == "completed"
    ).count()
    
    if completed_today == 0:
        # Streak broken!
        if profile.streak_shields_remaining > 0:
            # Create recovery mission
            recovery = Mission(
                title="Recover Your Streak",
                type="Recovery",
                difficulty=1,
                xp_reward=25,
                is_recovery=True,
                created_for_date=today,
                duration_minutes=10
            )
            db.add(recovery)
            db.commit()
            db.refresh(recovery)
            
            # Assign to user
            assign = MissionAssignment(
                user_id=user_id,
                mission_id=recovery.id,
                date=today,
                status="pending"
            )
            db.add(assign)
            db.commit()
            return True
    return False

def reset_shields_if_new_week(user_id: int, db: Session):
    """Reset shields to 2 when a new week starts."""
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return
    
    today = datetime.now()
    if profile.last_shield_reset_at is None:
        # First time
        profile.streak_shields_remaining = 2
        profile.last_shield_reset_at = today
        db.commit()
    else:
        # Check if week has advanced
        last_reset_week = profile.last_shield_reset_at.isocalendar()[1]
        today_week = today.isocalendar()[1]
        if last_reset_week != today_week:
            profile.streak_shields_remaining = 2
            profile.last_shield_reset_at = today
            db.commit()

def complete_recovery_mission(assignment_id: int, db: Session):
    """Complete a recovery mission: restore streak, consume shield."""
    assign = db.query(MissionAssignment).filter(MissionAssignment.id == assignment_id).first()
    if not assign:
        return
    
    assign.status = "completed"
    assign.used_streak_shield = True
    db.commit()
    
    # Restore streak
    profile = db.query(Profile).filter(Profile.user_id == assign.user_id).first()
    if profile:
        profile.streak_count += 1
        profile.streak_shields_remaining = max(0, profile.streak_shields_remaining - 1)
        db.commit()
