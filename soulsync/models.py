from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Text, Date, Float
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

class StoryEvent(Base):
    __tablename__ = "story_events"
    id = Column(Integer, primary_key=True)
    week_start_date = Column(String, unique=True, index=True)
    title = Column(String)
    theme = Column(String)
    trigger_rule_json = Column(JSON, default={})
    content_md = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserStoryUnlock(Base):
    __tablename__ = "user_story_unlocks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    story_event_id = Column(Integer, ForeignKey("story_events.id"))
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelApproval(Base):
    __tablename__ = "model_approvals"

    id = Column(Integer, primary_key=True)

    provider = Column(String, nullable=False)
    model_id = Column(String, nullable=False)
    modality = Column(String, nullable=False, default="text")
    # text | voice | multimodal

    status = Column(String, nullable=False, default="candidate")
    # candidate | evaluating | approved | rejected | rolled_back

    active = Column(Boolean, default=False)

    eval_score = Column(Float, nullable=True)
    eval_summary_json = Column(JSON, default={})
    capability_json = Column(JSON, default={})
    failure_json = Column(JSON, default={})

    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class NIMSEvaluationRun(Base):
    __tablename__ = "nims_evaluation_runs"

    id = Column(Integer, primary_key=True)

    approval_id = Column(Integer, ForeignKey("model_approvals.id"), nullable=False)

    status = Column(String, nullable=False, default="running")
    # running | passed | failed | error

    total_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    failed_cases = Column(Integer, default=0)

    score_json = Column(JSON, default={})
    case_results_json = Column(JSON, default={})
    audit_json = Column(JSON, default={})

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class NIMSRuntimeLog(Base):
    __tablename__ = "nims_runtime_logs"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_id = Column(Integer, ForeignKey("model_approvals.id"), nullable=True)

    user_text = Column(Text, nullable=True)
    raw_model_response = Column(Text, nullable=True)
    final_response = Column(Text, nullable=True)

    control_vector_json = Column(JSON, default={})
    arbitration_json = Column(JSON, default={})
    topic_ledger_json = Column(JSON, default={})
    guardrail_json = Column(JSON, default={})

    created_at = Column(DateTime(timezone=True), server_default=func.now())
