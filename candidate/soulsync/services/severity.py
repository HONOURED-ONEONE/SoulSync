from .time_service import utc_now
CATEGORY_SCORE={"study":2,"finance":3,"fitness":1,"sleep":1,"nutrition":1,"reflection":0,"social":0,"chores":1,"general":1}
RANK={"low":0,"medium":1,"high":2,"critical":3}
def calculate_severity(category,due_at_utc,now_utc=None):
    now_utc=now_utc or utc_now(); cp=CATEGORY_SCORE.get(category,1)
    if due_at_utc is None:
        score=cp; level="medium" if score>=2 else "low"; reason="No deadline supplied."
    else:
        if due_at_utc.tzinfo is None: due_at_utc=due_at_utc.replace(tzinfo=now_utc.tzinfo)
        hours=(due_at_utc-now_utc).total_seconds()/3600
        if hours<0: return {"level":"critical","score":cp+5,"reason":"Commitment is overdue.","calculated_at":now_utc}
        dp=4 if hours<=6 else 3 if hours<=24 else 2 if hours<=72 else 1 if hours<=168 else 0
        score=cp+dp; level="critical" if score>=6 else "high" if score>=4 else "medium" if score>=2 else "low"
        reason=f"{category or 'general'} commitment is due in {max(0,round(hours))} hours."
    return {"level":level,"score":score,"reason":reason,"calculated_at":now_utc}
def refresh_assignment_severity(assignment,mission,now_utc=None):
    result=calculate_severity(mission.type,assignment.due_at_utc,now_utc)
    assignment.severity=result["level"]; assignment.severity_score=result["score"]; assignment.severity_reason=result["reason"]; assignment.severity_calculated_at=result["calculated_at"]
    return result
