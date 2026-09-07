from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .errors import RetryableOperationError, RetryExhausted

T = TypeVar("T")


def retry_call(
    operation: Callable[[], T],
    *,
    recovery: Callable[[int, RetryableOperationError], None] | None = None,
    max_retries: int = 3,
) -> tuple[T, int, int]:
    """Execute once, then retry at most *max_retries* times.

    The default therefore permits at most four total attempts.
    """

    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")
    attempts = 0
    while True:
        attempts += 1
        try:
            return operation(), attempts, attempts - 1
        except RetryableOperationError as exc:
            retries_used = attempts - 1
            if retries_used >= max_retries:
                raise RetryExhausted(
                    f"Retryable operation failed after {attempts} total attempts",
                    attempts=attempts,
                    retries=retries_used,
                ) from exc
            if recovery is not None:
                recovery(attempts, exc)
