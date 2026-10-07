from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo

def utc_now(): return datetime.now(timezone.utc)
def get_timezone(name):
    try: return ZoneInfo(name or "UTC")
    except Exception: return ZoneInfo("UTC")
def local_now(name): return utc_now().astimezone(get_timezone(name))
def local_datetime_to_utc(value, name):
    if value.tzinfo is None: value=value.replace(tzinfo=get_timezone(name))
    return value.astimezone(timezone.utc)
def utc_datetime_to_local(value, name):
    if value.tzinfo is None: value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(get_timezone(name))
def local_day_bounds_utc(local_date, name):
    start=datetime.combine(local_date,time.min,tzinfo=get_timezone(name))
    return start.astimezone(timezone.utc),(start+timedelta(days=1)).astimezone(timezone.utc)


def as_aware_utc(value):
    """Normalize a persisted timestamp to aware UTC; SQLite commonly reloads it as naive."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
