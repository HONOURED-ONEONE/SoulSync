from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Text, Date
from sqlalchemy.sql import func
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    handle = Column(String)
    consent_leaderboard = Column(Boolean, default=False)
    consent_location = Column(Boolean, default=False)
    city = Column(String, nullable=True)
    region = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    avatar_url = Column(String, nullable=True)
    goals_json = Column(JSON, default={})
    timezone = Column(String, default="UTC")
    streak_count = Column(Integer, default=0)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    streak_shields_remaining = Column(Integer, default=2)
    last_shield_reset_at = Column(DateTime(timezone=True), nullable=True)
    day_end_time_local = Column(String, default="21:30")
    quiet_hours_start_local = Column(String, default="22:00")
    quiet_hours_end_local = Column(String, default="07:00")
    default_reminder_minutes = Column(Integer, default=60)

class Stat(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    type = Column(String)
    difficulty = Column(Integer, default=1)
    xp_reward = Column(Integer, default=10)
    is_hidden = Column(Boolean, default=False)
    is_recovery = Column(Boolean, default=False)
    geo_rule_json = Column(JSON, nullable=True)
    created_for_date = Column(String, nullable=True)
    created_by_system = Column(Boolean, default=True)
    duration_minutes = Column(Integer, nullable=True)

class MissionAssignment(Base):
    __tablename__ = "mission_assignments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mission_id = Column(Integer, ForeignKey("missions.id"))
    date = Column(String)
    status = Column(String, default="pending")
    proof_json = Column(JSON, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    used_streak_shield = Column(Boolean, default=False)
    plan_run_id = Column(Integer, ForeignKey("plan_runs.id"), nullable=True)
    earned_xp = Column(Integer, nullable=True)
    scheduled_at_utc = Column(DateTime(timezone=True), nullable=True)
    due_at_utc = Column(DateTime(timezone=True), nullable=True, index=True)
    source = Column(String, default="manual", nullable=False)
    severity = Column(String, default="low", nullable=False)
    severity_score = Column(Integer, default=0, nullable=False)
    severity_reason = Column(String, nullable=True)
    severity_calculated_at = Column(DateTime(timezone=True), nullable=True)
    next_notification_at_utc = Column(DateTime(timezone=True), nullable=True)
    last_notification_at_utc = Column(DateTime(timezone=True), nullable=True)
    notification_count = Column(Integer, default=0, nullable=False)
    notification_status = Column(String, default="not_scheduled", nullable=False)

class PlanRun(Base):
    __tablename__ = "plan_runs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    date = Column(String)
    plan_version = Column(Integer, default=1)
    source = Column(String)
    kind = Column(String)
    status = Column(String, default="previewed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meta_json = Column(JSON, default={})

class NotificationEvent(Base):
    __tablename__ = "notification_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("mission_assignments.id"), nullable=False, index=True)
    event_key = Column(String, nullable=False, unique=True, index=True)
    severity = Column(String, nullable=False)
    window = Column(String, nullable=False)
    channel = Column(String, nullable=False, default="in_app")
    status = Column(String, nullable=False, default="scheduled")
    scheduled_at_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    displayed_at_utc = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at_utc = Column(DateTime(timezone=True), nullable=True)
    snoozed_until_utc = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class VoiceMessage(Base):
    __tablename__ = "voice_messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)
    text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mood = Column(Integer)
    text = Column(Text)
    tags = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metrics_json = Column(JSON, default={})

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String)
    meta_json = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())








