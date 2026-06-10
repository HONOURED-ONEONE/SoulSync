"""
Deterministic turn-taking and repair policy for NIMS.
"""

from __future__ import annotations


CONFUSION_MARKERS = {
    "i don't get it",
    "i dont get it",
    "what?",
    "confusing",
    "too much",
    "i'm lost",
    "im lost",
    "explain again",
}


def compute_turn_policy(control_vector: dict) -> dict:
    """
    Computes deterministic turn policy.

    For Streamlit MVP, this policy is logged.
    Later, voice/TTS can enforce pause_before_ms.
    """

    return {
        "turn_latency_ms": int(control_vector.get("turn_latency_ms", 700)),
        "repair_mode": control_vector.get("repair_mode", "clarify_first"),
        "allow_immediate_response": False,
    }


def should_inject_repair(user_text: str, control_vector: dict) -> bool:
    lower = (user_text or "").lower()
    return any(marker in lower for marker in CONFUSION_MARKERS)


def build_repair_prompt() -> str:
    return (
        "Let's make this simpler. "
        "Which part feels unclear: the goal, the next step, or the timing?"
    )
