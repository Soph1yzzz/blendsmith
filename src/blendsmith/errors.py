class BlendSmithError(Exception):
    """Base error for expected BlendSmith failures."""


class ContractError(BlendSmithError):
    """A JSON contract failed validation or a runtime invariant."""


class StateTransitionError(BlendSmithError):
    """A requested lifecycle transition is invalid."""


class IntegrityError(BlendSmithError):
    """Artifact identity or integrity no longer matches recorded evidence."""


class SafetyError(BlendSmithError):
    """A filesystem or authority action is unsafe to perform automatically."""


class AuthorityError(BlendSmithError):
    """An owner-authority requirement was not satisfied."""


class CapabilityError(BlendSmithError):
    """A required capability is unusable or has an invalid downgrade."""


class RetryableOperationError(BlendSmithError):
    """An operation failed in a way that permits bounded recovery/retry."""


class RetryExhausted(BlendSmithError):
    """A retryable operation exhausted its retry budget."""

    def __init__(self, message: str, *, attempts: int, retries: int):
        super().__init__(message)
        self.attempts = attempts
        self.retries = retries
