from datetime import date
import streamlit as st
from soulsync.db import SessionLocal
from soulsync.models import Profile,PlanRun
from soulsync.services.time_service import utc_now,local_now
from soulsync.services.agenda import get_unified_agenda
from soulsync.services.notifications import get_due_notifications,snooze_notification,acknowledge_notification
from soulsync.services.commitment_proposals import extract_commitment_proposals,create_proposal_preview
from soulsync.services.missions import complete_mission
from soulsync.services.stats import get_stats
from soulsync.ui.theme import load_css
load_css()
if "user" not in st.session_state: st.warning("Please log in first."); st.stop()
user_id=st.session_state.user["id"]; tz=st.session_state.user.get("timezone","Asia/Kolkata"); db=SessionLocal()
try:
    st.title("Today's Agenda")
    capture=st.text_input("What do you need to do?")
    if st.button("Review commitment") and capture.strip():
        ps=extract_commitment_proposals(capture,local_now(tz))
        if ps: st.session_state["proposal_run_id"]=create_proposal_preview(user_id,date.today(),"dashboard","quick_capture_proposal",None,{},ps,db).id; st.info("Draft created. Review it in Journal before approval.")
        else: st.info("No explicit commitment detected.")
    due=get_due_notifications(user_id,utc_now(),db)
    if due:
        st.subheader("Alerts")
        for e in due:
            st.warning(f"{e.severity.title()}: {e.window}")
            c1,c2=st.columns(2)
            if c1.button("Snooze 15 min",key=f"sn{e.id}"): snooze_notification(e.id,user_id,15,db); st.rerun()
            if c2.button("Acknowledge",key=f"ak{e.id}"): acknowledge_notification(e.id,user_id,db); st.rerun()
    agenda=get_unified_agenda(user_id,local_now(tz).date(),tz,utc_now(),db)
    for key,label in [("overdue","Overdue"),("today","Today"),("coming_up","Coming Up"),("unscheduled","Unscheduled"),("completed_today","Completed Today")]:
        st.subheader(label)
        if not agenda[key]: st.caption("Nothing here.")
        for item in agenda[key]:
            a=item["assignment"]; m=item["mission"]
            st.markdown(f"**{m.title}** · {m.type} · {m.duration_minutes or '?'} min · {item.get('severity','low').title()}")
            if key!="completed_today" and st.button("Complete",key=f"done{a.id}"): complete_mission(a.id,db); st.rerun()
    st.divider(); profile=db.query(Profile).filter(Profile.user_id==user_id).first(); stats=get_stats(user_id,db)
    if profile: st.write(f"Streak: {profile.streak_count} 🔥 · Shields: {profile.streak_shields_remaining} 🛡️")
    st.write("XP",{x.type:x.xp for x in stats})
finally: db.close()
