from __future__ import annotations
from copy import deepcopy
from uuid import uuid4
import re
from datetime import datetime,timedelta,time
from ..models import PlanRun,Mission,MissionAssignment,AuditLog
from .time_service import local_datetime_to_utc,utc_now
from .severity import refresh_assignment_severity
from .notifications import schedule_notifications_for_assignment
ALLOWED_CATEGORIES={"study","finance","fitness","sleep","nutrition","reflection","social","chores","general"}
PROPOSAL_STATUSES={"draft","needs_input","verified","assigned","dismissed","superseded"}
def new_blank_proposal(): return {"proposal_id":uuid4().hex,"status":"draft","title":None,"category":None,"scheduled_date":None,"scheduled_time":None,"deadline_date":None,"deadline_time":None,"estimated_minutes":None,"reminder_minutes_before":None,"notes":None,"source_excerpt":None,"field_sources":{},"missing_fields":[]}
def _int(v,zero=False):
    try: n=int(v)
    except: return None
    return n if ((n>=0) if zero else (n>0)) else None
def normalize_proposal(c):
    c=deepcopy(c) if isinstance(c,dict) else {}; r=new_blank_proposal()
    for k in ["proposal_id","status","title","category","scheduled_date","scheduled_time","deadline_date","deadline_time","notes","source_excerpt"]:
        if k in c:
            value=c[k]
            if isinstance(value,str): value=value.strip() or None
            r[k]=value
    if isinstance(r["category"],str): r["category"]=r["category"].lower()
    if r["category"] not in ALLOWED_CATEGORIES: r["category"]=None
    if r["status"] not in PROPOSAL_STATUSES: r["status"]="draft"
    r["estimated_minutes"]=_int(c.get("estimated_minutes")); r["reminder_minutes_before"]=_int(c.get("reminder_minutes_before"),True)
    r["field_sources"]=deepcopy(c.get("field_sources")) if isinstance(c.get("field_sources"),dict) else {}
    return find_missing_fields(r)
def find_missing_fields(p):
    p=deepcopy(p); missing=[k for k in ("title","category","estimated_minutes") if not p.get(k)]
    if not (p.get("scheduled_date") or p.get("deadline_date")): missing.append("scheduled_date_or_deadline_date")
    p["missing_fields"]=missing
    if p.get("status") not in {"assigned","dismissed","superseded"}: p["status"]="needs_input" if missing else "verified"
    return p
def _category(x):
    x=x.lower(); maps={"finance":["pay","fee","budget","expense"],"study":["study","exam","assignment","submit","revise"],"fitness":["gym","workout","exercise","run"],"chores":["clean","laundry","wash"],"social":["call","meet","message"],"reflection":["reflect","journal"]}
    for c,words in maps.items():
        if any(w in x for w in words): return c
    return "general" if re.search(r"\b(do|finish|prepare|attend|buy|send|complete)\b",x) else None
def extract_commitment_proposals(text,now_local,use_ai=True):
    proposals=[]
    for segment in re.split(r"[\n.!?]+", text):
        segment=segment.strip()
        cat=_category(segment)
        if not segment or not cat: continue
        p=new_blank_proposal(); p["title"]=re.sub(r"\b(today|tomorrow|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?|for \d+ minutes?)\b","",segment,flags=re.I).strip(" ,-")
        p["category"]=cat; p["source_excerpt"]=segment; p["field_sources"]={"title":"extracted","category":"extracted"}
        if re.search(r"\btomorrow\b",segment,re.I): p["scheduled_date"]=(now_local.date()+timedelta(days=1)).isoformat()
        elif re.search(r"\btoday\b",segment,re.I): p["scheduled_date"]=now_local.date().isoformat()
        iso=re.search(r"\b\d{4}-\d{2}-\d{2}\b",segment)
        if iso: p["scheduled_date"]=iso.group()
        dur=re.search(r"\b(?:for\s+)?(\d+)\s*(?:minutes?|mins?)\b",segment,re.I)
        if dur: p["estimated_minutes"]=int(dur.group(1))
        tm=re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",segment,re.I)
        if tm:
            h=int(tm.group(1)); m=int(tm.group(2) or 0); ap=tm.group(3).lower(); h=(h%12)+(12 if ap=='pm' else 0); p["scheduled_time"]=f"{h:02d}:{m:02d}"
        proposals.append(normalize_proposal(p))
    seen=set(); out=[]
    for p in proposals:
        key=(p["title"].lower(),p.get("scheduled_date"),p.get("deadline_date"))
        if key not in seen: seen.add(key); out.append(p)
    return out
def create_proposal_preview(user_id,local_date,source,kind,journal_entry_id,signals,proposals,db):
    run=PlanRun(user_id=user_id,date=str(local_date),source=source,kind=kind,status="previewed",meta_json={"journal_entry_id":journal_entry_id,"signals":signals,"proposals":[normalize_proposal(x) for x in proposals],"schema_version":1})
    db.add(run); db.commit(); db.refresh(run); return run
def _mutate(plan_run_id,proposal_id,user_id,db,fn):
    run=db.query(PlanRun).filter(PlanRun.id==plan_run_id,PlanRun.user_id==user_id).first()
    if not run: raise ValueError("Proposal batch not found")
    meta=deepcopy(run.meta_json or {}); found=False
    items=[]
    for p in meta.get("proposals",[]):
        if p.get("proposal_id")==proposal_id: p=fn(deepcopy(p)); found=True
        items.append(p)
    if not found: raise ValueError("Proposal not found")
    meta["proposals"]=items; run.meta_json=meta; db.commit(); return next(x for x in items if x.get("proposal_id")==proposal_id)
def update_proposal(plan_run_id,proposal_id,values,user_id,db):
    def f(p):
        if p.get("status") in {"assigned","dismissed","superseded"}: raise ValueError("Proposal is locked")
        p.update({k:v for k,v in values.items() if k in p and k not in {"proposal_id","status"}}); return normalize_proposal(p)
    return _mutate(plan_run_id,proposal_id,user_id,db,f)
def dismiss_proposal(plan_run_id,proposal_id,user_id,db):
    return _mutate(plan_run_id,proposal_id,user_id,db,lambda p:{**p,"status":"dismissed"} if p.get("status")!="assigned" else (_ for _ in ()).throw(ValueError("Assigned proposal cannot be dismissed")))
def approve_proposal(user_id,plan_run_id,proposal_id,edited_values,db,timezone_name="UTC"):
    run=db.query(PlanRun).filter(PlanRun.id==plan_run_id,PlanRun.user_id==user_id).first()
    if not run: raise ValueError("Proposal batch not found")
    meta=deepcopy(run.meta_json or {}); items=meta.get("proposals",[]); p=next((x for x in items if x.get("proposal_id")==proposal_id),None)
    if not p: raise ValueError("Proposal not found")
    if p.get("status")=="assigned": return db.query(MissionAssignment).filter(MissionAssignment.id==p.get("assignment_id")).first()
    p.update({k:v for k,v in edited_values.items() if k in p}); p=normalize_proposal(p)
    if p["missing_fields"]: raise ValueError("Missing: "+", ".join(p["missing_fields"]))
    def dt(date_s,time_s):
        if not date_s or not time_s: return None
        return local_datetime_to_utc(datetime.combine(datetime.fromisoformat(date_s).date(),datetime.strptime(time_s,"%H:%M").time()),timezone_name)
    scheduled=dt(p.get("scheduled_date"),p.get("scheduled_time")); due=dt(p.get("deadline_date"),p.get("deadline_time"))
    mission=Mission(title=p["title"],type=p["category"],duration_minutes=p["estimated_minutes"],xp_reward=max(5,min(50,p["estimated_minutes"]//2)),created_by_system=False)
    db.add(mission); db.flush()
    a=MissionAssignment(user_id=user_id,mission_id=mission.id,date=p.get("scheduled_date") or p.get("deadline_date"),status="pending",plan_run_id=run.id,source=run.source or "journal",scheduled_at_utc=scheduled,due_at_utc=due)
    db.add(a); db.flush(); refresh_assignment_severity(a,mission,utc_now()); schedule_notifications_for_assignment(a,utc_now(),db)
    for i,x in enumerate(items):
        if x.get("proposal_id")==proposal_id: p["status"]="assigned"; p["assignment_id"]=a.id; items[i]=p
    meta["proposals"]=items; run.meta_json=meta
    db.add(AuditLog(user_id=user_id,event_type="commitment_approved",meta_json={"plan_run_id":run.id,"proposal_id":proposal_id,"assignment_id":a.id}))
    db.commit(); db.refresh(a); return a
