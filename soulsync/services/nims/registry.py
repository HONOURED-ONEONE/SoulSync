"""
NIMS model registry helpers.

Responsible for registering candidate models, looking up active approved
models, activating approved models, and rollback.
"""

from __future__ import annotations

from datetime import datetime, timezone

from soulsync.models import ModelApproval
from soulsync.services.nims.errors import NoApprovedModelError


def register_candidate_model(
    db,
    provider: str,
    model_id: str,
    modality: str = "text",
    capabilities: dict | None = None,
) -> int:
    """
    Creates a candidate model record.

    Example:
        approval_id = register_candidate_model(
            db,
            provider="gemini",
            model_id="gemini-1.5-flash",
            modality="text",
            capabilities={"supports_streaming": False}
        )
    """

    record = ModelApproval(
        provider=provider,
        model_id=model_id,
        modality=modality,
        status="candidate",
        active=False,
        capability_json=capabilities or {},
        eval_summary_json={},
        failure_json={},
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record.id


def get_model_approval(db, approval_id: int) -> ModelApproval:
    """
    Fetches one ModelApproval record by id.
    """

    record = db.query(ModelApproval).filter(ModelApproval.id == approval_id).first()

    if record is None:
        raise NoApprovedModelError(f"No model approval record found for id={approval_id}")

    return record


def get_active_approved_model(db) -> ModelApproval:
    """
    Returns the active approved model.

    Raises:
        NoApprovedModelError if no active approved model exists.
    """

    record = (
        db.query(ModelApproval)
        .filter(ModelApproval.status == "approved")
        .filter(ModelApproval.active == True)  # noqa: E712
        .order_by(ModelApproval.approved_at.desc())
        .first()
    )

    if record is None:
        raise NoApprovedModelError("No active approved NIMS model is available.")

    return record


def activate_approved_model(db, approval_id: int) -> None:
    """
    Activates an approved model and deactivates all others.
    """

    target = get_model_approval(db, approval_id)

    if target.status != "approved":
        raise ValueError(
            f"Cannot activate model id={approval_id}; status is '{target.status}', not 'approved'."
        )

    db.query(ModelApproval).update({ModelApproval.active: False})

    target.active = True
    target.approved_at = target.approved_at or datetime.now(timezone.utc)

    db.add(target)
    db.commit()


def reject_model(db, approval_id: int, reason: str, failure_json: dict | None = None) -> None:
    """
    Marks a candidate/evaluating model as rejected.
    """

    record = get_model_approval(db, approval_id)
    record.status = "rejected"
    record.active = False
    record.rejected_at = datetime.now(timezone.utc)
    record.failure_json = failure_json or {"reason": reason}

    db.add(record)
    db.commit()


def rollback_active_model(db, approval_id: int | None = None) -> None:
    """
    Rolls back the current active model.

    If approval_id is provided, activates that approved model.
    Otherwise, deactivates all models and leaves Your Voice in fallback mode.
    """

    db.query(ModelApproval).update({ModelApproval.active: False})
    db.commit()

    if approval_id is not None:
        activate_approved_model(db, approval_id)
