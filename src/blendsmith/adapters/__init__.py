"""Optional host adapters for BlendSmith."""

from .mcp import BlenderMCPAdapter, MCPTransport

__all__ = ["BlenderMCPAdapter", "MCPTransport"]
