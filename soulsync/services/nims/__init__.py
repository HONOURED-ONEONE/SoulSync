"""
NIMS - Neurodivergent Interaction Modelling System.

Internal SoulSync extension for candidate model governance,
evaluation, approval, and runtime interaction safety.
"""

from .errors import (
    NIMSError,
    NoApprovedModelError,
    ModelEvaluationFailed,
    RuntimeGuardRejected,
)

from .registry import (
    register_candidate_model,
    get_active_approved_model,
    activate_approved_model,
    rollback_active_model,
)

from .eval_harness import run_model_evaluation
from .runtime_guard import run_nims_guarded_turn

__all__ = [
    "NIMSError",
    "NoApprovedModelError",
    "ModelEvaluationFailed",
    "RuntimeGuardRejected",
    "register_candidate_model",
    "get_active_approved_model",
    "activate_approved_model",
    "rollback_active_model",
    "run_model_evaluation",
    "run_nims_guarded_turn",
]
