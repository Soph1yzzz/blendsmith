from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from ..errors import CapabilityError, RetryableOperationError, RetryExhausted, SafetyError
from ..retry import retry_call

_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class MCPTransport(Protocol):
    """Host-supplied MCP transport.

    BlendSmith deliberately does not own an MCP client SDK. A host can inject its
    existing transport while BlendSmith keeps tool allowlisting and response checks.
    """

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class BlenderMCPAdapter:
    transport: MCPTransport
    allowed_tools: frozenset[str]

    def __post_init__(self) -> None:
        if not self.allowed_tools:
            raise ValueError("At least one MCP tool must be allowlisted")
        for name in self.allowed_tools:
            if not _TOOL_NAME.fullmatch(name):
                raise ValueError(f"Invalid MCP tool name: {name}")

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.allowed_tools:
            raise SafetyError(f"MCP tool is not allowlisted: {tool_name}")
        if not isinstance(arguments, dict):
            raise TypeError("MCP arguments must be an object")
        response = self.transport.call(tool_name, arguments)
        if not isinstance(response, dict):
            raise CapabilityError("MCP adapter expected an object response")
        return response

    def probe(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            try:
                return self.call(tool_name, arguments or {})
            except SafetyError:
                raise
            except (TypeError, ValueError):
                raise
            except Exception as exc:
                raise RetryableOperationError(f"MCP probe failed: {tool_name}") from exc

        try:
            response, attempts, retries = retry_call(operation, max_retries=3)
        except RetryExhausted as exc:
            return {
                "status": "BROKEN",
                "details": {
                    "error": type(exc).__name__,
                    "tool": tool_name,
                    "attempts": exc.attempts,
                    "retries": exc.retries,
                },
            }
        return {
            "status": "AVAILABLE",
            "details": {
                "tool": tool_name,
                "response": response,
                "attempts": attempts,
                "retries": retries,
            },
        }
