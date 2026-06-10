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
    "Register, evaluate, approve, and activate candidate models for Your Voice."
)

show_nims_admin = st.checkbox("Show NIMS research controls", value=False)

if show_nims_admin:
    st.subheader("Register Candidate Model")

    candidate_provider = st.text_input("Provider", value="fallback")
    candidate_model_id = st.text_input("Model ID", value="fallback")
    candidate_modality = st.selectbox(
        "Modality",
        options=["text", "voice", "multimodal"],
        index=0,
    )

    if st.button("Register Candidate Model"):
        if register_candidate_model is None:
            st.error("NIMS registry is unavailable.")
        else:
            approval_id = register_candidate_model(
                db=db,
                provider=candidate_provider,
                model_id=candidate_model_id,
                modality=candidate_modality,
                capabilities={
                    "registered_from": "settings_page",
                },
            )
            st.success(f"Registered candidate model with approval_id={approval_id}")

    st.subheader("Candidate / Approved Models")

    if ModelApproval is None:
        st.warning("ModelApproval model unavailable.")
    else:
        records = db.query(ModelApproval).order_by(ModelApproval.id.desc()).limit(20).all()

        if not records:
            st.info("No NIMS model records yet.")
        else:
            for record in records:
                st.write(
                    {
                        "id": record.id,
                        "provider": record.provider,
                        "model_id": record.model_id,
                        "modality": record.modality,
                        "status": record.status,
                        "active": record.active,
                        "eval_score": record.eval_score,
                    }
                )

    st.subheader("Run Evaluation")

    eval_approval_id = st.number_input(
        "Approval ID to evaluate",
        min_value=1,
        step=1,
    )

    if st.button("Run NIMS Evaluation"):
        if run_model_evaluation is None:
            st.error("NIMS evaluation harness is unavailable.")
        else:
            try:
                result = run_model_evaluation(db, int(eval_approval_id))
                st.success(f"Evaluation completed: {result['decision']}")
                st.json(result)
            except Exception as exc:
                st.error(f"Evaluation failed: {exc}")

    st.subheader("Activate Approved Model")

    activate_approval_id = st.number_input(
        "Approval ID to activate",
        min_value=1,
        step=1,
        key="nims_activate_approval_id",
    )

    if st.button("Activate Approved Model"):
        if activate_approved_model is None:
            st.error("NIMS activation function is unavailable.")
        else:
            try:
                activate_approved_model(db, int(activate_approval_id))
                st.success(f"Activated approved model id={activate_approval_id}")
            except Exception as exc:
                st.error(f"Activation failed: {exc}")

    st.subheader("Rollback")

    if st.button("Deactivate All NIMS Models"):
        if rollback_active_model is None:
            st.error("NIMS rollback function is unavailable.")
        else:
            try:
                rollback_active_model(db)
                st.warning("All NIMS models deactivated. Your Voice will use fallback behavior if configured.")
            except Exception as exc:
                st.error(f"Rollback failed: {exc}")

    st.subheader("Active Model")

    if get_active_approved_model is not None:
        try:
            active_model = get_active_approved_model(db)
            st.success(
                f"Active: id={active_model.id}, "
                f"provider={active_model.provider}, "
                f"model={active_model.model_id}"
            )
        except Exception:
            st.info("No active approved NIMS model.")

st.divider()

if st.button("Logout"):
    del st.session_state.user
    db.close()
    st.rerun()

db.close()
