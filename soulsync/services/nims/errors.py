class NIMSError(Exception):
    """Base exception for all NIMS-related failures."""
    pass


class NoApprovedModelError(NIMSError):
    """Raised when Your Voice requires an approved model but none is active."""
    pass


class ModelEvaluationFailed(NIMSError):
    """Raised when a candidate model fails deterministic NIMS evaluation."""
    pass


class RuntimeGuardRejected(NIMSError):
    """Raised when a live model response is rejected by runtime NIMS guardrails."""
    pass
