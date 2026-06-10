"""
NIMS runtime guard.

Applies approved-model lookup and deterministic runtime guardrails for
Your Voice interactions.
"""


def run_nims_guarded_turn(
    db,
    user_id: int,
    user_text: str,
    voice_mode: str,
    context: str | None = None,
) -> dict:
    raise NotImplementedError("NIMS runtime guard is not implemented yet.")
