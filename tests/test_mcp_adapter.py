from __future__ import annotations

import pytest

from blendsmith.adapters.mcp import BlenderMCPAdapter
from blendsmith.errors import SafetyError


class FailingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def call(self, tool_name: str, arguments: dict) -> dict:
        self.calls += 1
        raise RuntimeError("temporary transport failure")


class SuccessTransport:
    def __init__(self) -> None:
        self.calls = 0

    def call(self, tool_name: str, arguments: dict) -> dict:
        self.calls += 1
        return {"ok": True}


def test_probe_uses_initial_attempt_plus_three_retries() -> None:
    transport = FailingTransport()
    adapter = BlenderMCPAdapter(transport=transport, allowed_tools=frozenset({"probe.scene"}))
    result = adapter.probe("probe.scene")
    assert result["status"] == "BROKEN"
    assert result["details"]["attempts"] == 4
    assert result["details"]["retries"] == 3
    assert transport.calls == 4


def test_probe_does_not_downgrade_allowlist_violation_to_broken() -> None:
    transport = SuccessTransport()
    adapter = BlenderMCPAdapter(transport=transport, allowed_tools=frozenset({"probe.scene"}))
    with pytest.raises(SafetyError):
        adapter.probe("dangerous.tool")
    assert transport.calls == 0
