"""
Audit helpers for NIMS evaluation and runtime decisions.
"""

from __future__ import annotations

from soulsync.models import NIMSRuntimeLog


def log_evaluation_event(db, approval_id: int, event_type: str, payload: dict) -> None:
    """
    Placeholder for future AuditLog integration.

    If SoulSync has an AuditLog model, this function can be expanded to write there.
    For now, evaluation data is stored in NIMSEvaluationRun.
    """
    return None


def log_runtime_decision(
    db,
    user_id: int | None,
    approval_id: int | None,
    user_text: str,
    raw_response: str,
    final_response: str,
    metadata: dict,
) -> None:
    """
    Writes a NIMSRuntimeLog row.
    """

    record = NIMSRuntimeLog(
        user_id=user_id,
        approval_id=approval_id,
        user_text=user_text,
        raw_model_response=raw_response,
        final_response=final_response,
        control_vector_json=metadata.get("control_vector", {}),
        arbitration_json=metadata.get("arbitration", {}),
        topic_ledger_json=metadata.get("topic_ledger", {}),
        guardrail_json=metadata.get("guardrail", {}),
    )

    db.add(record)
    db.commit()
