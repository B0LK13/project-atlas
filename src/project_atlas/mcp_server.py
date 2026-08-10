"""AS-2.1-MCP-SERVER-001 - read-first MCP-style JSON tool server.

Exposes allow-listed read tools over stdio JSON lines. No vault writes.
Requires authz mcp.read. Does not load remote MCP SDKs.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from project_atlas.app_service import AppService, open_app_service
from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import require_compatibility_anchor
from project_atlas.mcp_registry import DEFAULT_TOOLS

PACKAGE_ID = "AS-2.1-MCP-SERVER-001"
TRUTH_BOUNDARY = "MCP_READ LIVE != WRITE / != AUTHORITY / != ESTATE SCAN"


class McpServerError(ValueError):
    """Fail-closed MCP read server error."""


def _enabled_read_tools() -> frozenset[str]:
    return frozenset(
        t.tool_id for t in DEFAULT_TOOLS if t.enabled and t.tool_class == "vault-read"
    )


def build_tool_dispatch(service: AppService) -> Mapping[str, Callable[[], dict[str, Any]]]:
    """Map allow-listed tool ids to AppService callables."""
    return {
        "atlas.ops.health.read": lambda: service.health(),
        "atlas.knowledge.query.read": lambda: {"knowledge": service.knowledge()},
        "atlas.explain.receipt.read": lambda: {
            "note": "explain receipts via snapshot graph/health only",
            "graph": service.graph_summary(),
        },
    }


def list_mcp_tools(
    *,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Return allow-listed read tool inventory (no execution)."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("mcp.read")
    tools = sorted(_enabled_read_tools())
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "tools": tools,
        "write_tools": [],
        "live_mcp_read": True,
        "operator_id": op.operator_id,
        "generated": {"by": "project-atlas"},
    }


def invoke_mcp_tool(
    vault: Path,
    tool_id: str,
    *,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Invoke one allow-listed read tool against a vault."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("mcp.read")
    if tool_id not in _enabled_read_tools():
        raise McpServerError(f"mcp-tool-denied:{tool_id}")
    service = open_app_service(vault)
    dispatch = build_tool_dispatch(service)
    if tool_id not in dispatch:
        raise McpServerError(f"mcp-tool-unbound:{tool_id}")
    result = dispatch[tool_id]()
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "tool_id": tool_id,
        "live_mcp_read": True,
        "result": result,
        "generated": {"by": "project-atlas"},
    }


def handle_mcp_request_line(
    vault: Path,
    line: str,
    *,
    operator: OperatorProfile | None = None,
) -> str:
    """Handle one JSON-line request: {\"tool\": \"...\"} -> JSON response."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise McpServerError(f"mcp-json-invalid:{exc}") from exc
    if not isinstance(payload, dict):
        raise McpServerError("mcp-request-not-object")
    tool = payload.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise McpServerError("mcp-tool-missing")
    response = invoke_mcp_tool(vault, tool.strip(), operator=operator)
    return json.dumps(response, sort_keys=True)
