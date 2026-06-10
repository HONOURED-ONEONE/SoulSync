import streamlit as st
from soulsync.config import get_diagnostics
from soulsync.db import SessionLocal
from soulsync.models import Profile
from soulsync.services.story_service import get_unlocked_stories
from soulsync.ui.theme import load_css

try:
    from soulsync.services.nims.registry import (
        register_candidate_model,
        activate_approved_model,
        rollback_active_model,
    )
    from soulsync.services.nims.eval_harness import run_model_evaluation
    from soulsync.services.nims.registry import get_active_approved_model
    from soulsync.models import ModelApproval
except Exception:
    register_candidate_model = None
    activate_approved_model = None
    rollback_active_model = None
    run_model_evaluation = None
    get_active_approved_model = None
    ModelApproval = None

load_css()
st.title("Settings ⚙️")

db = SessionLocal()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    db.close()
    st.stop()

user_id = st.session_state.user["id"]
profile = db.query(Profile).filter(Profile.user_id == user_id).first()

st.subheader("My Day Ends At")
st.write("Used to keep plans and swaps realistic: after this time, only wind-down missions are suggested.")

if profile:
    current_time = profile.day_end_time_local or "21:30"
else:
    current_time = "21:30"

time_input = st.time_input("Day end time (local)", value=None)

if time_input:
    time_str = time_input.strftime("%H:%M")
    if profile:
        profile.day_end_time_local = time_str
    else:
        profile = Profile(user_id=user_id, day_end_time_local=time_str)
        db.add(profile)
    db.commit()
    st.success(f"✅ Day end time saved: {time_str}")
else:
    # Show current value
    st.write(f"**Current setting:** {current_time}")

st.divider()

st.subheader("Diagnostics")
diag = get_diagnostics()
st.json(diag)

st.divider()

st.subheader("Storybook 📚")
stories = get_unlocked_stories(user_id, db) if profile else []
if stories:
    for story in stories:
        with st.expander(f"{story.title} ({story.week_start_date})"):
            st.markdown(story.content_md)
else:
    st.write("No stories unlocked yet. Keep completing missions!")

st.divider()
st.header("NIMS Model Governance")
st.caption(
    "NIMS model registration, evaluation, activation, rollback, and runtime "
    "log inspection are now available in the dedicated NIMS Evaluation page."
)
st.info("Open the NIMS Evaluation page from the Streamlit sidebar.")

st.divider()

if st.button("Logout"):
    del st.session_state.user
    db.close()
    st.rerun()

db.close()
