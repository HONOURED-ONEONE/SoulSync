from sqlalchemy import create_engine,text,inspect
from sqlalchemy.orm import sessionmaker,declarative_base
from .config import DATABASE_URL
connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {}
engine=create_engine(DATABASE_URL,connect_args=connect_args)
SessionLocal=sessionmaker(bind=engine,autocommit=False,autoflush=False)
Base=declarative_base()
def init_db():
    from . import models
    Base.metadata.create_all(bind=engine); ensure_schema()
def ensure_schema():
    additions={
      "profiles":{"streak_shields_remaining":"INTEGER DEFAULT 2","last_shield_reset_at":"TIMESTAMP NULL","day_end_time_local":"VARCHAR DEFAULT '21:30'","quiet_hours_start_local":"VARCHAR DEFAULT '22:00'","quiet_hours_end_local":"VARCHAR DEFAULT '07:00'","default_reminder_minutes":"INTEGER DEFAULT 60"},
      "missions":{"is_recovery":"BOOLEAN DEFAULT FALSE","duration_minutes":"INTEGER NULL"},
      "mission_assignments":{"used_streak_shield":"BOOLEAN DEFAULT FALSE","plan_run_id":"INTEGER","earned_xp":"INTEGER","scheduled_at_utc":"TIMESTAMP NULL","due_at_utc":"TIMESTAMP NULL","source":"VARCHAR DEFAULT 'manual'","severity":"VARCHAR DEFAULT 'low'","severity_score":"INTEGER DEFAULT 0","severity_reason":"VARCHAR NULL","severity_calculated_at":"TIMESTAMP NULL","next_notification_at_utc":"TIMESTAMP NULL","last_notification_at_utc":"TIMESTAMP NULL","notification_count":"INTEGER DEFAULT 0","notification_status":"VARCHAR DEFAULT 'not_scheduled'"}}
    with engine.begin() as conn:
        ins=inspect(conn)
        for table,cols in additions.items():
            if not ins.has_table(table): continue
            existing={c['name'] for c in ins.get_columns(table)}
            for name,sqltype in cols.items():
                if name not in existing: conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"))
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
