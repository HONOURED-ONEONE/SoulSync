"""
NIMS model registry helpers.

Responsible for registering, approving, activating, and rolling back
candidate models.
"""


def register_candidate_model(db, provider: str, model_id: str, modality: str, capabilities: dict) -> int:
    raise NotImplementedError("NIMS model registry is not implemented yet.")


def get_active_approved_model(db):
    raise NotImplementedError("NIMS active model lookup is not implemented yet.")
