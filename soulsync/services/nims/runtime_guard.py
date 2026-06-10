"""
NIMS runtime guard.

Main live interaction path for Your Voice.
"""

from __future__ import annotations

from soulsync.services.nims.adapters import generate_candidate_response
from soulsync.services.nims.arbitration import arbitrate_response
from soulsync.services.nims.audit import log_runtime_decision
from soulsync.services.nims.config import NIMS_REQUIRE_APPROVED_MODEL
from soulsync.services.nims.registry import get_active_approved_model
from soulsync.services.nims.topic_ledger import (
    initialize_topic_ledger,
    update_topic_ledger,
    build_topic_bridge_response,
)
from soulsync.services.nims.turn_policy import (
    compute_turn_policy,
    should_inject_repair,
    build_repair_prompt,
)
from soulsync.services.nims.errors import NoApprovedModelError

try:
    from soulsync.services.voice_intent import get_voice_intent_features
except Exception:
    get_voice_intent_features = None

try:
    from soulsync.services.journal_signals import get_nims_safe_journal_signals
except Exception:
    get_nims_safe_journal_signals = None

try:
    from soulsync.services.missions import get_nims_time_context
except Exception:
    get_nims_time_context = None

try:
    from soulsync.services.moderation import check_nims_runtime_safety
except Exception:
    check_nims_runtime_safety = None


def _build_control_vector(
    user_text: str,
    voice_mode: str,
    context: str | None = None,
    voice_features: dict | None = None,
    journal_signals: dict | None = None,
    time_context: dict | None = None,
) -> dict:
    """
    Deterministically derives interaction control vector.

    Inputs are aggregate signals only.
    No raw journal content should enter this function.
    """

    lower = (user_text or "").lower()
    voice_features = voice_features or {}
    journal_signals = journal_signals or {}
    time_context = time_context or {}

    control = {
        "literalness": "high",
        "topic_adherence": "medium",
        "response_length": "short",
        "repair_mode": "clarify_first",
        "turn_latency_ms": 700,
        "cognitive_load": "low",
    }

    if voice_mode in {"planning", "planner", "mission"}:
        control["topic_adherence"] = "high"
        control["response_length"] = "short"

    if voice_features.get("has_confusion"):
        control["repair_mode"] = "clarify_first"
        control["turn_latency_ms"] = 900

    if voice_features.get("has_planning_intent"):
        control["topic_adherence"] = "high"

    if voice_features.get("has_emotional_intensity"):
        control["response_length"] = "short"
        control["cognitive_load"] = "low"

    if journal_signals.get("stress") == "high":
        control["response_length"] = "short"
        control["cognitive_load"] = "low"

    if journal_signals.get("energy") == "low":
        control["turn_latency_ms"] = max(control["turn_latency_ms"], 900)
        control["response_length"] = "short"

    if time_context.get("after_day_end"):
        control["response_length"] = "short"
        control["cognitive_load"] = "low"
        control["turn_latency_ms"] = max(control["turn_latency_ms"], 900)

    if any(marker in lower for marker in ["too much", "overwhelmed", "confusing", "lost"]):
        control["cognitive_load"] = "low"
        control["response_length"] = "short"
        control["turn_latency_ms"] = max(control["turn_latency_ms"], 900)

    return control


def run_nims_guarded_turn(
    db,
    user_id: int,
    user_text: str,
    voice_mode: str,
    context: str | None = None,
    topic_ledger: dict | None = None,
) -> dict:
    """
    Main runtime entry point for Your Voice.

    Flow:
        1. Load active approved model.
        2. Build deterministic control vector.
        3. Update topic ledger.
        4. Optionally inject repair response.
        5. Generate raw candidate response.
        6. Apply deterministic arbitration.
        7. Log runtime decision.
        8. Return final governed response.
    """

    try:
        active_model = get_active_approved_model(db)
    except NoApprovedModelError:
        if NIMS_REQUIRE_APPROVED_MODEL:
            raise

        active_model = None

    voice_features = {}
    journal_signals = {}
    time_context = {}

    if get_voice_intent_features is not None:
        try:
            voice_features = get_voice_intent_features(user_text)
        except Exception:
            voice_features = {}

    if get_nims_safe_journal_signals is not None:
        try:
            journal_signals = get_nims_safe_journal_signals(user_id=user_id, db=db)
        except Exception:
            journal_signals = {}

    if get_nims_time_context is not None:
        try:
            time_context = get_nims_time_context()
        except Exception:
            time_context = {}

    control_vector = _build_control_vector(
        user_text=user_text,
        voice_mode=voice_mode,
        context=context,
        voice_features=voice_features,
        journal_signals=journal_signals,
        time_context=time_context,
    )

    if topic_ledger is None:
        topic_ledger = initialize_topic_ledger(user_text=user_text, context=context)
    else:
        topic_ledger = update_topic_ledger(
            ledger=topic_ledger,
            user_text=user_text,
            control_vector=control_vector,
        )

    turn_policy = compute_turn_policy(control_vector)

    if topic_ledger.get("last_switch_allowed") is False:
        raw_response = build_topic_bridge_response(topic_ledger)
    elif should_inject_repair(user_text, control_vector):
        raw_response = build_repair_prompt()
    else:
        if active_model is None:
            provider = "fallback"
            model_id = "fallback"
        else:
            provider = active_model.provider
            model_id = active_model.model_id

        raw_response = generate_candidate_response(
            provider=provider,
            model_id=model_id,
            user_text=user_text,
            context=context,
            voice_mode=voice_mode,
        )

    arbitration = arbitrate_response(
        raw_response=raw_response,
        control_vector=control_vector,
        context=context,
    )

    final_text = arbitration["final_text"]

    moderation_result = {"safe": True, "flags": []}

    if check_nims_runtime_safety is not None:
        try:
            moderation_result = check_nims_runtime_safety(final_text)
        except Exception:
            moderation_result = {"safe": True, "flags": ["moderation_check_error"]}

    if not moderation_result.get("safe", True):
        final_text = (
            "I want to keep this safe and clear. "
            "Let's focus on one simple next step."
        )

    guardrail = {
        "approved_model_required": NIMS_REQUIRE_APPROVED_MODEL,
        "active_model_id": active_model.id if active_model is not None else None,
        "runtime_status": "allowed",
        "voice_features": voice_features,
        "journal_signal_source": journal_signals.get("source"),
        "time_context_source": time_context.get("source"),
        "moderation": moderation_result,
        "topic_similarity": topic_ledger.get("last_similarity"),
        "topic_switch_threshold": topic_ledger.get("switch_threshold"),
        "topic_switch_allowed": topic_ledger.get("last_switch_allowed"),
        "topic_governance": topic_ledger.get("governance"),
    }

    metadata = {
        "control_vector": control_vector,
        "arbitration": arbitration,
        "topic_ledger": topic_ledger,
        "turn_policy": turn_policy,
        "guardrail": guardrail,
    }

    log_runtime_decision(
        db=db,
        user_id=user_id,
        approval_id=active_model.id if active_model is not None else None,
        user_text=user_text,
        raw_response=raw_response,
        final_response=final_text,
        metadata=metadata,
    )

    return {
        "final_text": final_text,
        "raw_model_response": raw_response,
        "control_vector": control_vector,
        "topic_ledger": topic_ledger,
        "arbitration": arbitration,
        "turn_policy": turn_policy,
        "guardrail": guardrail,
    }
