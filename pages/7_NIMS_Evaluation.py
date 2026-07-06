import streamlit as st

try:
    from soulsync.db import SessionLocal
except Exception:
    SessionLocal = None

try:
    from soulsync.models import ModelApproval, NIMSEvaluationRun, NIMSRuntimeLog
except Exception:
    ModelApproval = None
    NIMSEvaluationRun = None
    NIMSRuntimeLog = None

try:
    from soulsync.services.nims.registry import (
        register_candidate_model,
        activate_approved_model,
        rollback_active_model,
        get_active_approved_model,
    )
    from soulsync.services.nims.eval_harness import run_model_evaluation
except Exception:
    register_candidate_model = None
    activate_approved_model = None
    rollback_active_model = None
    get_active_approved_model = None
    run_model_evaluation = None

try:
    from soulsync.services.nims.evaluation_cases import NIMS_EVALUATION_CASES
except Exception:
    NIMS_EVALUATION_CASES = []

try:
    from soulsync.services.nims.topic_ledger import (
        initialize_topic_ledger,
        update_topic_ledger,
    )
except Exception:
    initialize_topic_ledger = None
    update_topic_ledger = None


st.set_page_config(
    page_title="NIMS Evaluation",
    page_icon="🧭",
    layout="wide",
)

st.title("NIMS Evaluation Dashboard")
st.caption(
    "Evaluate, approve, activate, and monitor candidate models for SoulSync Your Voice."
)

if SessionLocal is None:
    st.error("Database session is unavailable. Check soulsync.database.SessionLocal.")
    st.stop()

db = SessionLocal()

st.info(
    "NIMS evaluates interaction properties such as clarity, predictability, "
    "topic stability, repair behavior, cognitive-load control, and privacy discipline. "
    "It does not diagnose users or simulate neurodivergent identity."
)

st.divider()
st.header("1. Active Approved Model")

if get_active_approved_model is None:
    st.warning("NIMS registry functions are unavailable.")
else:
    try:
        active_model = get_active_approved_model(db)
        st.success(
            f"Active model: id={active_model.id}, "
            f"provider={active_model.provider}, "
            f"model={active_model.model_id}, "
            f"score={active_model.eval_score}"
        )
        st.json(active_model.eval_summary_json or {})
    except Exception:
        st.info("No active approved NIMS model is currently set.")

st.divider()
st.header("2. Register Candidate Model")

with st.form("nims_register_candidate_form"):
    candidate_provider = st.text_input("Provider", value="fallback")
    candidate_model_id = st.text_input("Model ID", value="fallback")
    candidate_modality = st.selectbox(
        "Modality",
        options=["text", "voice", "multimodal"],
        index=0,
    )

    supports_streaming = st.checkbox("Supports streaming", value=False)
    supports_asr = st.checkbox("Supports ASR", value=False)
    supports_tts = st.checkbox("Supports TTS", value=False)

    submitted = st.form_submit_button("Register Candidate")

    if submitted:
        if register_candidate_model is None:
            st.error("register_candidate_model is unavailable.")
        else:
            approval_id = register_candidate_model(
                db=db,
                provider=candidate_provider,
                model_id=candidate_model_id,
                modality=candidate_modality,
                capabilities={
                    "supports_streaming": supports_streaming,
                    "supports_asr": supports_asr,
                    "supports_tts": supports_tts,
                    "registered_from": "nims_evaluation_dashboard",
                },
            )

            st.success(f"Candidate registered with approval_id={approval_id}")

st.divider()
st.header("3. Model Registry")

if ModelApproval is None:
    st.warning("ModelApproval model is unavailable.")
else:
    records = (
        db.query(ModelApproval)
        .order_by(ModelApproval.id.desc())
        .limit(50)
        .all()
    )

    if not records:
        st.info("No candidate models registered yet.")
    else:
        registry_rows = []

        for record in records:
            registry_rows.append(
                {
                    "id": record.id,
                    "provider": record.provider,
                    "model_id": record.model_id,
                    "modality": record.modality,
                    "status": record.status,
                    "active": record.active,
                    "eval_score": record.eval_score,
                    "approved_at": str(record.approved_at) if record.approved_at else None,
                    "rejected_at": str(record.rejected_at) if record.rejected_at else None,
                }
            )

        st.dataframe(registry_rows, use_container_width=True)

st.divider()
st.header("4. Run NIMS Evaluation")

eval_col_1, eval_col_2 = st.columns([1, 2])

with eval_col_1:
    eval_approval_id = st.number_input(
        "Approval ID",
        min_value=1,
        step=1,
        key="nims_eval_approval_id",
    )

    run_eval = st.button("Run Evaluation", type="primary")

with eval_col_2:
    st.write("Evaluation case count:", len(NIMS_EVALUATION_CASES))

    with st.expander("Preview evaluation cases"):
        st.json(NIMS_EVALUATION_CASES)

if run_eval:
    if run_model_evaluation is None:
        st.error("run_model_evaluation is unavailable.")
    else:
        with st.spinner("Running deterministic NIMS evaluation..."):
            try:
                result = run_model_evaluation(db, int(eval_approval_id))
                st.success("Evaluation completed.")
                st.json(result)
            except Exception as exc:
                st.error(f"Evaluation failed: {exc}")

st.divider()
st.header("5. Activate or Roll Back Model")

activate_col, rollback_col = st.columns(2)

with activate_col:
    activate_id = st.number_input(
        "Approved model ID to activate",
        min_value=1,
        step=1,
        key="nims_activate_id",
    )

    if st.button("Activate Approved Model"):
        if activate_approved_model is None:
            st.error("activate_approved_model is unavailable.")
        else:
            try:
                activate_approved_model(db, int(activate_id))
                st.success(f"Activated model id={activate_id}")
            except Exception as exc:
                st.error(f"Activation failed: {exc}")

with rollback_col:
    st.warning("Rollback deactivates all active NIMS models.")

    if st.button("Deactivate All Active Models"):
        if rollback_active_model is None:
            st.error("rollback_active_model is unavailable.")
        else:
            try:
                rollback_active_model(db)
                st.success("All active NIMS models were deactivated.")
            except Exception as exc:
                st.error(f"Rollback failed: {exc}")

st.divider()
st.header("6. Evaluation Run History")

if NIMSEvaluationRun is None:
    st.warning("NIMSEvaluationRun model is unavailable.")
else:
    runs = (
        db.query(NIMSEvaluationRun)
        .order_by(NIMSEvaluationRun.id.desc())
        .limit(25)
        .all()
    )

    if not runs:
        st.info("No NIMS evaluation runs yet.")
    else:
        run_rows = []

        for run in runs:
            run_rows.append(
                {
                    "run_id": run.id,
                    "approval_id": run.approval_id,
                    "status": run.status,
                    "total_cases": run.total_cases,
                    "passed_cases": run.passed_cases,
                    "failed_cases": run.failed_cases,
                    "started_at": str(run.started_at) if run.started_at else None,
                    "completed_at": str(run.completed_at) if run.completed_at else None,
                }
            )

        st.dataframe(run_rows, use_container_width=True)

        selected_run_id = st.number_input(
            "Inspect run ID",
            min_value=1,
            step=1,
            key="nims_inspect_run_id",
        )

        if st.button("Inspect Evaluation Run"):
            selected_run = (
                db.query(NIMSEvaluationRun)
                .filter(NIMSEvaluationRun.id == int(selected_run_id))
                .first()
            )

            if selected_run is None:
                st.error("Evaluation run not found.")
            else:
                st.subheader(f"Run {selected_run.id} Details")
                st.json(
                    {
                        "score_json": selected_run.score_json,
                        "case_results_json": selected_run.case_results_json,
                        "audit_json": selected_run.audit_json,
                    }
                )

st.divider()
st.header("7. Runtime Governance Logs")

if NIMSRuntimeLog is None:
    st.warning("NIMSRuntimeLog model is unavailable.")
else:
    logs = (
        db.query(NIMSRuntimeLog)
        .order_by(NIMSRuntimeLog.id.desc())
        .limit(25)
        .all()
    )

    if not logs:
        st.info("No NIMS runtime logs yet.")
    else:
        log_rows = []

        for log in logs:
            guardrail = log.guardrail_json or {}
            arbitration = log.arbitration_json or {}
            topic_ledger = log.topic_ledger_json or {}

            log_rows.append(
                {
                    "log_id": log.id,
                    "user_id": log.user_id,
                    "approval_id": log.approval_id,
                    "topic_similarity": guardrail.get("topic_similarity"),
                    "topic_threshold": guardrail.get("topic_switch_threshold"),
                    "topic_switch_allowed": guardrail.get("topic_switch_allowed"),
                    "arbitration_changed": arbitration.get("changed"),
                    "topic": topic_ledger.get("current_topic"),
                    "created_at": str(log.created_at) if log.created_at else None,
                }
            )

        st.dataframe(log_rows, use_container_width=True)

        selected_log_id = st.number_input(
            "Inspect runtime log ID",
            min_value=1,
            step=1,
            key="nims_inspect_runtime_log_id",
        )

        if st.button("Inspect Runtime Log"):
            selected_log = (
                db.query(NIMSRuntimeLog)
                .filter(NIMSRuntimeLog.id == int(selected_log_id))
                .first()
            )

            if selected_log is None:
                st.error("Runtime log not found.")
            else:
                st.subheader(f"Runtime Log {selected_log.id}")
                st.write("User text")
                st.code(selected_log.user_text or "")

                st.write("Raw model response")
                st.code(selected_log.raw_model_response or "")

                st.write("Final governed response")
                st.code(selected_log.final_response or "")

                st.write("Governance metadata")
                st.json(
                    {
                        "control_vector": selected_log.control_vector_json,
                        "arbitration": selected_log.arbitration_json,
                        "topic_ledger": selected_log.topic_ledger_json,
                        "guardrail": selected_log.guardrail_json,
                    }
                )

st.divider()
st.header("8. Topic Ledger Simulator")

st.caption(
    "Use this panel to test deterministic embedding-similarity governance "
    "without calling a candidate LLM."
)

if initialize_topic_ledger is None or update_topic_ledger is None:
    st.warning("Topic ledger functions are unavailable.")
else:
    initial_topic_text = st.text_area(
        "Initial topic/context",
        value="I need help planning my math homework.",
        key="nims_topic_initial",
    )

    new_turn_text = st.text_area(
        "New user turn",
        value="Can we talk about cricket highlights instead?",
        key="nims_topic_new_turn",
    )

    adherence = st.selectbox(
        "Topic adherence level",
        options=["high", "medium", "low"],
        index=0,
    )

    if st.button("Simulate Topic Governance"):
        sim_ledger = initialize_topic_ledger(
            user_text=initial_topic_text,
            context=None,
        )

        sim_ledger = update_topic_ledger(
            ledger=sim_ledger,
            user_text=new_turn_text,
            control_vector={"topic_adherence": adherence},
        )

        st.json(
            {
                "current_topic": sim_ledger.get("current_topic"),
                "last_similarity": sim_ledger.get("last_similarity"),
                "switch_threshold": sim_ledger.get("switch_threshold"),
                "last_switch_allowed": sim_ledger.get("last_switch_allowed"),
                "topic_strength": sim_ledger.get("topic_strength"),
                "governance": sim_ledger.get("governance"),
            }
        )

        if sim_ledger.get("last_switch_allowed"):
            st.success("Topic switch allowed by hard threshold.")
        else:
            st.error("Topic switch blocked by hard threshold.")

try:
    db.close()
except Exception:
    pass
