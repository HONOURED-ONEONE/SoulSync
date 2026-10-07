from sqlalchemy.orm import Session
from ..models import Stat

STATS_TYPES = ["Knowledge", "Guts", "Proficiency", "Kindness", "Charm"]

def init_stats(user_id: int, db: Session):
    for s_type in STATS_TYPES:
        stat = Stat(user_id=user_id, type=s_type, level=1, xp=0)
        db.add(stat)
    db.commit()

def get_stats(user_id: int, db: Session):
    return db.query(Stat).filter(Stat.user_id == user_id).all()

def add_xp(user_id: int, stat_type: str, amount: int, db: Session):
    stat = db.query(Stat).filter(Stat.user_id == user_id, Stat.type == stat_type).first()
    if stat:
        stat.xp += amount
        # Simple level up logic: level * 100
        required_xp = stat.level * 100
        if stat.xp >= required_xp:
            stat.level += 1
            stat.xp -= required_xp
        db.commit()
