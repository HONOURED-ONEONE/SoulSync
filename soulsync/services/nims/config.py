"""
Local NIMS configuration bridge.

This module prevents all NIMS files from importing global project config
directly and gives us one stable import point.
"""

from soulsync.config import (
    NIMS_ENABLED,
    NIMS_REQUIRE_APPROVED_MODEL,
    NIMS_DEBUG_PANEL,
    NIMS_DEFAULT_PROVIDER,
    NIMS_DEFAULT_MODEL_ID,
    NIMS_MIN_APPROVAL_SCORE,
    NIMS_MAX_SAFETY_FAILURES,
    NIMS_MAX_TOPIC_FAILURES,
    NIMS_MAX_LITERALNESS_FAILURES,
)

__all__ = [
    "NIMS_ENABLED",
    "NIMS_REQUIRE_APPROVED_MODEL",
    "NIMS_DEBUG_PANEL",
    "NIMS_DEFAULT_PROVIDER",
    "NIMS_DEFAULT_MODEL_ID",
    "NIMS_MIN_APPROVAL_SCORE",
    "NIMS_MAX_SAFETY_FAILURES",
    "NIMS_MAX_TOPIC_FAILURES",
    "NIMS_MAX_LITERALNESS_FAILURES",
]
