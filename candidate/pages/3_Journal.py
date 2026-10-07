from datetime import datetime,date
import streamlit as st
from soulsync.db import SessionLocal
from soulsync.models import PlanRun
from soulsync.services.journal import add_entry
from soulsync.services.journal_signals import extract_journal_signals
from soulsync.services.commitment_proposals import extract_commitment_proposals,create_proposal_preview,update_proposal,dismiss_proposal,approve_proposal
from soulsync.services.time_service import local_now
from soulsync.ui.theme import load_css
load_css()
if "user" not in st.session_state: st.warning("Please log in first."); st.stop()
st.title("Daily Journal ✍️")
user_id=st.session_state.user["id"]; tz=st.session_state.user.get("timezone","Asia/Kolkata")
with st.form("journal"):
    text=st.text_area("What happened, and what do you need to do?"); mood=st.slider("Mood",1,5,3); submitted=st.form_submit_button("Save and review commitments")
if submitted and text.strip():
    db=SessionLocal()
    try:
        entry=add_entry(user_id,text,mood,{"mood":mood},db); signals=extract_journal_signals(entry.text,mood_label=None)
        entry.metrics_json={**(entry.metrics_json or {}),"signals":signals,"signal_schema_version":1}; db.commit()
        proposals=extract_commitment_proposals(text,local_now(tz)); run=create_proposal_preview(user_id,date.today(),"journal","journal_commitment_proposals",entry.id,signals,proposals,db) if proposals else None
        st.session_state["proposal_run_id"]=run.id if run else None; st.success("Journal saved. Review any detected commitment drafts below.")
    finally: db.close()
run_id=st.session_state.get("proposal_run_id")
if run_id:
    db=SessionLocal()
    try:
        run=db.query(PlanRun).filter(PlanRun.id==run_id,PlanRun.user_id==user_id).first()
        if run:
            st.subheader("Review commitment drafts")
            for p in (run.meta_json or {}).get("proposals",[]):
                if p.get("status") in {"dismissed","assigned"}: continue
                with st.expander(p.get("title") or "Untitled draft",expanded=True):
                    title=st.text_input("Title",p.get("title") or "",key=f"t{p['proposal_id']}")
                    category=st.selectbox("Category",["", "study","finance","fitness","sleep","nutrition","reflection","social","chores","general"],index=(["", "study","finance","fitness","sleep","nutrition","reflection","social","chores","general"].index(p.get("category") or "")),key=f"c{p['proposal_id']}")
                    d=st.text_input("Scheduled date (YYYY-MM-DD)",p.get("scheduled_date") or "",key=f"d{p['proposal_id']}")
                    tm=st.text_input("Time (HH:MM, optional)",p.get("scheduled_time") or "",key=f"tm{p['proposal_id']}")
                    mins=st.number_input("Estimated minutes",min_value=0,value=int(p.get("estimated_minutes") or 0),key=f"m{p['proposal_id']}")
                    vals={"title":title,"category":category or None,"scheduled_date":d or None,"scheduled_time":tm or None,"estimated_minutes":mins or None}
                    if p.get("missing_fields"): st.warning("Missing: "+", ".join(p["missing_fields"]))
                    a,b,c=st.columns(3)
                    if a.button("Save draft",key=f"s{p['proposal_id']}"): update_proposal(run.id,p["proposal_id"],vals,user_id,db); st.rerun()
                    if b.button("Dismiss",key=f"x{p['proposal_id']}"): dismiss_proposal(run.id,p["proposal_id"],user_id,db); st.rerun()
                    if c.button("Approve",key=f"a{p['proposal_id']}"):
                        try: approve_proposal(user_id,run.id,p["proposal_id"],vals,db,tz); st.success("Commitment approved."); st.rerun()
                        except ValueError as e: st.error(str(e))
    finally: db.close()
