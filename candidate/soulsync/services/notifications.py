from datetime import timedelta
from ..models import NotificationEvent, MissionAssignment
from .time_service import utc_now, as_aware_utc
POLICY={"low":[],"medium":[("day_of",0)],"high":[("24_hours",1440),("2_hours",120)],"critical":[("immediate",None),("overdue",-1)]}
def schedule_notifications_for_assignment(a,now_utc=None,db=None):
    now_utc=now_utc or utc_now(); events=[]
    for window,minutes in POLICY.get(a.severity,[]):
        anchor=a.due_at_utc or a.scheduled_at_utc
        if minutes is None: when=now_utc
        elif anchor is None: continue
        elif minutes==-1: when=anchor
        else: when=anchor-timedelta(minutes=minutes)
        if when<now_utc and window not in {"immediate","overdue"}: continue
        key=f"{a.id}:{a.severity}:{window}:{when.isoformat()}"
        event=db.query(NotificationEvent).filter(NotificationEvent.event_key==key).first()
        if not event:
            event=NotificationEvent(user_id=a.user_id,assignment_id=a.id,event_key=key,severity=a.severity,window=window,scheduled_at_utc=when,status="due" if when<=now_utc else "scheduled")
            db.add(event); db.flush()
        events.append(event)
    a.notification_count=len(events); a.next_notification_at_utc=min((e.scheduled_at_utc for e in events if e.status in {"scheduled","due","snoozed"}),default=None); a.notification_status="scheduled" if events else "agenda_only"
    return events
def get_due_notifications(user_id,now_utc,db):
    now_utc = as_aware_utc(now_utc)
    rows = db.query(NotificationEvent).filter(
        NotificationEvent.user_id == user_id,
        NotificationEvent.channel == "in_app",
    ).all()
    due = []
    for event in rows:
        if event.status not in {"scheduled", "due", "snoozed"}:
            continue
        effective_at = as_aware_utc(event.snoozed_until_utc or event.scheduled_at_utc)
        if effective_at is not None and effective_at <= now_utc:
            due.append(event)
    return due
def acknowledge_notification(event_id,user_id,db,now_utc=None):
    e=db.query(NotificationEvent).filter(NotificationEvent.id==event_id,NotificationEvent.user_id==user_id).first()
    if e and e.status!="acknowledged": e.status="acknowledged"; e.acknowledged_at_utc=now_utc or utc_now(); db.commit()
    return e
def snooze_notification(event_id,user_id,minutes,db,now_utc=None):
    if minutes<=0: raise ValueError("minutes must be positive")
    e=db.query(NotificationEvent).filter(NotificationEvent.id==event_id,NotificationEvent.user_id==user_id).first()
    if e: e.status="snoozed"; e.snoozed_until_utc=(now_utc or utc_now())+timedelta(minutes=minutes); db.commit()
    return e
def close_assignment_notifications(assignment_id,db,status="completed"):
    for e in db.query(NotificationEvent).filter(NotificationEvent.assignment_id==assignment_id).all():
        if e.status in {"scheduled","due","snoozed","displayed"}: e.status=status
