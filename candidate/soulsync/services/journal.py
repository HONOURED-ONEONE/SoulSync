from sqlalchemy.orm import Session
from ..models import JournalEntry

def add_entry(user_id: int, text: str, mood: int, metrics: dict, db: Session):
    entry = JournalEntry(
        user_id=user_id,
        text=text,
        mood=mood,
        metrics_json=metrics
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

def get_recent_entries(user_id: int, db: Session, limit=3):
    return db.query(JournalEntry).filter(JournalEntry.user_id == user_id).order_by(JournalEntry.created_at.desc()).limit(limit).all()
