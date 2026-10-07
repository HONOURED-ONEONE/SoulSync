import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.models import Mission, PlanRun
from soulsync.services.missions import (
    get_todays_missions,
    complete_mission,
    build_planner_context,
    generate_ai_plan_json,
    validate_plan,
    preview_plan,
    assign_plan_creating_daily_missions,
    compute_time_context,
    get_pending_missions,
    propose_swaps,
    validate_swap_plan,
    apply_swaps,
    can_mark_micro_now,
    mark_micro_completed,
)
from soulsync.services.streak import (
    reset_shields_if_new_week,
    complete_recovery_mission,
)
from soulsync.services.mood_suggester import suggest_mood_actions
from soulsync.services.party import (
    get_or_create_party_roster,
    propose_party_missions,
    apply_party_missions,
)
from soulsync.ui.theme import load_css

# Deprecated: the standalone Missions page has been removed from the active MVP.
# This module is intentionally kept as a compatibility stub so stale links do not crash.
# Users are directed to the Dashboard for active planning and completion workflows.

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Missions page removed")
st.warning("This page is no longer part of the active MVP. Open the Dashboard to continue.")

if st.button("Open Dashboard"):
    try:
        st.switch_page("pages/1_Dashboard.py")
    except Exception:
        st.info("Open the Dashboard from the sidebar to continue.")
