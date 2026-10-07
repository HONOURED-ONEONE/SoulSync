from sqlalchemy.orm import Session
from ..models import Profile

DEFAULT_TIMEZONE = "Asia/Kolkata"

def get_or_create_profile(user_id: int, db: Session) -> Profile:
    """Return the user's Profile, creating it without committing the caller's transaction."""
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is None:
        profile = Profile(
            user_id=user_id,
            timezone=DEFAULT_TIMEZONE,
            streak_count=0,
            streak_shields_remaining=2,
            day_end_time_local="21:30",
            quiet_hours_start_local="22:00",
            quiet_hours_end_local="07:00",
            default_reminder_minutes=60,
        )
        db.add(profile)
        db.flush()
    return profile
