from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from soulsync.db import Base
from soulsync.models import User, Profile, Mission, MissionAssignment, NotificationEvent
from soulsync.services.profile_service import get_or_create_profile
from soulsync.services.notifications import get_due_notifications


def make_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo-blockers.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def test_new_user_gets_one_profile_with_demo_defaults(tmp_path):
    db, engine = make_session(tmp_path)
    user = User(email="new@example.com", handle="New")
    db.add(user); db.flush()
    first = get_or_create_profile(user.id, db)
    second = get_or_create_profile(user.id, db)
    db.commit()
    assert first.id == second.id
    assert db.query(Profile).filter(Profile.user_id == user.id).count() == 1
    assert first.timezone == "Asia/Kolkata"
    assert first.day_end_time_local == "21:30"
    db.close(); engine.dispose()


def test_due_notification_survives_sqlite_reload(tmp_path):
    db, engine = make_session(tmp_path)
    user = User(email="alerts@example.com", handle="Alerts")
    db.add(user); db.flush()
    mission = Mission(title="Pay fee", type="finance")
    db.add(mission); db.flush()
    assignment = MissionAssignment(user_id=user.id, mission_id=mission.id, date="2026-10-07", status="pending")
    db.add(assignment); db.flush()
    now = datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc)
    event = NotificationEvent(
        user_id=user.id,
        assignment_id=assignment.id,
        event_key="reload-probe",
        severity="high",
        window="2_hours",
        channel="in_app",
        status="scheduled",
        scheduled_at_utc=now - timedelta(minutes=1),
    )
    db.add(event); db.commit(); user_id = user.id; db.close()
    Session = sessionmaker(bind=engine); db = Session()
    rows = get_due_notifications(user_id, now, db)
    assert [row.event_key for row in rows] == ["reload-probe"]
    db.close(); engine.dispose()
