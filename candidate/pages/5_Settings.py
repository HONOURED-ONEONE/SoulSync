from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from soulsync.config import get_diagnostics
from soulsync.db import SessionLocal
from soulsync.models import Profile
from soulsync.services.profile_service import get_or_create_profile
from soulsync.ui.theme import load_css
load_css(); st.title("Settings ⚙️")
if "user" not in st.session_state: st.warning("Please log in first."); st.stop()
db=SessionLocal()
try:
 p=get_or_create_profile(st.session_state.user["id"],db)
 db.commit(); db.refresh(p)
 st.subheader("Timezone"); tz=st.text_input("IANA timezone",p.timezone or "Asia/Kolkata")
 st.subheader("Day end and quiet hours")
 def parse(v,d):
  try:return datetime.strptime(v or d,"%H:%M").time()
  except:return datetime.strptime(d,"%H:%M").time()
 day=st.time_input("Day end",parse(p.day_end_time_local,"21:30")); qs=st.time_input("Quiet hours start",parse(p.quiet_hours_start_local,"22:00")); qe=st.time_input("Quiet hours end",parse(p.quiet_hours_end_local,"07:00")); rem=st.number_input("Default reminder minutes",0,10080,int(p.default_reminder_minutes or 60))
 if st.button("Save settings"):
  try: ZoneInfo(tz)
  except: st.error("Invalid timezone")
  else: p.timezone=tz;p.day_end_time_local=day.strftime("%H:%M");p.quiet_hours_start_local=qs.strftime("%H:%M");p.quiet_hours_end_local=qe.strftime("%H:%M");p.default_reminder_minutes=int(rem);db.commit();st.session_state.user["timezone"]=p.timezone;st.success("Settings saved")
 st.subheader("Diagnostics");st.json(get_diagnostics())
 if st.button("Logout"): del st.session_state.user;st.rerun()
finally:db.close()
