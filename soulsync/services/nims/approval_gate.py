"""
NIMS approval gate.

Converts deterministic evaluation summaries into approve/reject decisions.
"""

from __future__ import annotations

from soulsync.services.nims.config import (
    NIMS_MIN_APPROVAL_SCORE,
    NIMS_MAX_SAFETY_FAILURES,
    NIMS_MAX_TOPIC_FAILURES,
    NIMS_MAX_LITERALNESS_FAILURES,
)


def decide_model_approval(eval_summary: dict) -> dict:
    """
    Returns deterministic approval decision.

    Expected input:
        {
            "score": 0.91,
            "failure_counts": {
                "privacy": 0,
                "topic_adherence": 1,
                "literalness": 0
            }
        }
    """

    score = float(eval_summary.get("score", 0.0))
    failures = eval_summary.get("failure_counts", {}) or {}

    if score < NIMS_MIN_APPROVAL_SCORE:
        return {
            "approved": False,
            "reason": "score_below_threshold",
            "score": score,
        }

    privacy_failures = failures.get("privacy", 0)
    if privacy_failures > NIMS_MAX_SAFETY_FAILURES:
        return {
            "approved": False,
            "reason": "privacy_or_safety_failures_exceeded",
            "score": score,
            "failure_count": privacy_failures,
        }

    topic_failures = failures.get("topic_adherence", 0)
    if topic_failures > NIMS_MAX_TOPIC_FAILURES:
        return {
            "approved": False,
            "reason": "topic_failures_exceeded",
            "score": score,
            "failure_count": topic_failures,
        }

    literalness_failures = failures.get("literalness", 0)
    if literalness_failures > NIMS_MAX_LITERALNESS_FAILURES:
        return {
            "approved": False,
            "reason": "literalness_failures_exceeded",
            "score": score,
            "failure_count": literalness_failures,
        }

    return {
        "approved": True,
        "reason": "passed_all_thresholds",
        "score": score,
    }
