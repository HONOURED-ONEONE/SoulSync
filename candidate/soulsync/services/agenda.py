from datetime import datetime,date
from ..models import MissionAssignment,Mission
from .time_service import local_day_bounds_utc,utc_datetime_to_local
from .severity import refresh_assignment_severity,RANK
def get_unified_agenda(user_id,local_date,timezone_name,now_utc,db):
    out={"overdue":[],"today":[],"coming_up":[],"unscheduled":[],"completed_today":[]}; start,end=local_day_bounds_utc(local_date,timezone_name)
    rows=db.query(MissionAssignment,Mission).join(Mission,Mission.id==MissionAssignment.mission_id).filter(MissionAssignment.user_id==user_id).all()
    for a,m in rows:
        if a.status=="completed":
            if a.completed_at:
                c=a.completed_at if a.completed_at.tzinfo else a.completed_at.replace(tzinfo=now_utc.tzinfo)
                if start<=c<end: out["completed_today"].append({"assignment":a,"mission":m,"severity":a.severity})
            continue
        if a.status not in {"pending","assigned"}: continue
        refresh_assignment_severity(a,m,now_utc); item={"assignment":a,"mission":m,"severity":a.severity,"score":a.severity_score,"reason":a.severity_reason}
        if a.due_at_utc:
            due=a.due_at_utc if a.due_at_utc.tzinfo else a.due_at_utc.replace(tzinfo=now_utc.tzinfo)
            if due<now_utc: out["overdue"].append(item); continue
            if start<=due<end: out["today"].append(item); continue
            if due>=end: out["coming_up"].append(item); continue
        if a.scheduled_at_utc:
            sch=a.scheduled_at_utc if a.scheduled_at_utc.tzinfo else a.scheduled_at_utc.replace(tzinfo=now_utc.tzinfo)
            if start<=sch<end: out["today"].append(item)
            elif sch>=end: out["coming_up"].append(item)
            else: out["unscheduled"].append(item)
        elif a.date==local_date.isoformat(): out["today"].append(item)
        elif a.date and a.date>local_date.isoformat(): out["coming_up"].append(item)
        else: out["unscheduled"].append(item)
    for key in ("overdue","today","coming_up","unscheduled"): out[key].sort(key=lambda x:(-RANK.get(x["severity"],0),x["assignment"].due_at_utc or x["assignment"].scheduled_at_utc or datetime.max))
    out["completed_today"].sort(key=lambda x:x["assignment"].completed_at or datetime.min,reverse=True)
    return out
