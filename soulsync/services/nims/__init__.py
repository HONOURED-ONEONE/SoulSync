"""
NIMS - Neurodivergent Interaction Modelling System

Internal SoulSync extension for candidate model governance,
evaluation, approval, and runtime interaction safety.
"""

from .errors import NIMSError, NoApprovedModelError, ModelEvaluationFailed, RuntimeGuardRejected

__all__ = [
    "NIMSError",
    "NoApprovedModelError",
    "ModelEvaluationFailed",
    "RuntimeGuardRejected",
]
