from __future__ import annotations

import pytest

from blendsmith.errors import RetryableOperationError, RetryExhausted
from blendsmith.retry import retry_call


def test_initial_attempt_plus_three_retries_can_succeed_on_fourth_call() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 4:
            raise RetryableOperationError("temporary")
        return "ok"

    result, attempts, retries = retry_call(operation)
    assert result == "ok"
    assert attempts == 4
    assert retries == 3
    assert calls == 4


def test_retry_exhaustion_is_four_total_attempts() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise RetryableOperationError("temporary")

    with pytest.raises(RetryExhausted) as captured:
        retry_call(operation)
    assert calls == 4
    assert captured.value.attempts == 4
    assert captured.value.retries == 3
