"""AS-2.1-MCP-SERVER-001 - read-first MCP-style JSON tool server.

Exposes allow-listed read tools over stdio JSON lines. No vault writes.
Requires authz mcp.read. Does not load remote MCP SDKs.

AS-2.1-MCP-ADV-001 hardens request parsing: unknown tools, write escalation,
path traversal, and malformed args fail closed. MCP stays READ ONLY.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

from project_atlas.app_service import AppService, AppServiceError, open_app_service
from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import require_compatibility_anchor
from project_atlas.mcp_registry import DEFAULT_TOOLS
from project_atlas.web_mission_workspace import (
    build_mission_view,
    build_workspace_view,
)

PACKAGE_ID = "AS-2.1-MCP-SERVER-001"
ADV_PACKAGE_ID = "AS-2.1-MCP-ADV-001"
BRIEF_PACKAGE_ID = "AS-2.1-MCP-BRIEF-001"
ROADMAP_PACKAGE_ID = "AS-CODER-ALPHA-ROADMAP-MCP-001"
MISSION_WS_PACKAGE_ID = "AS-CODER-ALPHA-MISSION-WORKSPACE-MCP-001"
GRAPH_PACKAGE_ID = "AS-CODER-ALPHA-GRAPH-MCP-001"
TRUTH_BOUNDARY = "MCP_READ LIVE != WRITE / != AUTHORITY / != ESTATE SCAN"
BRIEF_TRUTH_BOUNDARY = (
    "MCP BRIEF != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)
ROADMAP_TRUTH_BOUNDARY = (
    "MCP ROADMAP != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL / ROADMAP != CANONICAL"
)
MISSION_WS_TRUTH_BOUNDARY = (
    "MCP MISSION/WORKSPACE != AUTHORITY / NO PILOT INVENT / NO WRITE / "
    "UI != CANONICAL / AUTHENTIC_PILOT = FALSE"
)
GRAPH_TRUTH_BOUNDARY = (
    "MCP GRAPH != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "ABSENT GRAPH != FABRICATED EDGES"
)

# Allow-listed request keys for JSON-line invoke (no path/write/args surface).
_ALLOWED_REQUEST_KEYS: Final[frozenset[str]] = frozenset({"tool"})
_FORBIDDEN_REQUEST_KEYS: Final[frozenset[str]] = frozenset(
    {
        "path",
        "paths",
        "file",
        "files",
        "vault",
        "write",
        "content",
        "payload",
        "args",
        "arguments",
        "params",
        "parameters",
        "cwd",
        "target",
        "destination",
        "output",
    }
)
_TOOL_ID_SAFE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9.-]{0,127}$")


class McpServerError(ValueError):
    """Fail-closed MCP read server error."""


def _enabled_read_tools() -> frozenset[str]:
    return frozenset(
        t.tool_id for t in DEFAULT_TOOLS if t.enabled and t.tool_class == "vault-read"
    )


def _assert_safe_tool_id(tool_id: str) -> str:
    """Reject path traversal / malformed tool identifiers before dispatch."""
    tid = tool_id.strip()
    if not tid:
        raise McpServerError("mcp-tool-missing")
    if "\x00" in tid:
        raise McpServerError("mcp-tool-id-nul")
    lowered = tid.lower()
    if (
        ".." in tid
        or "/" in tid
        or "\\" in tid
        or ":" in tid
        or tid.startswith(".")
        or "%2e" in lowered
        or "%2f" in lowered
        or "%5c" in lowered
    ):
        raise McpServerError(f"mcp-tool-path-traversal:{tid}")
    if not _TOOL_ID_SAFE_RE.fullmatch(tid):
        raise McpServerError(f"mcp-tool-id-malformed:{tid}")
    return tid


def _unknown_brief_row(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "purpose": "UNKNOWN",
        "available": False,
        "suggested_next_work": [],
        "honesty": {
            "unknown_is_valid": True,
            "lens_is_authority": False,
            "fabricated_fields": False,
        },
    }


def read_vault_briefs(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped brief read. Does not invent projects or write."""
    rows: list[dict[str, Any]] = []
    for project in service.projects():
        pid = str(project.get("project_id") or "").strip()
        if not pid:
            continue
        try:
            brief = service.brief(pid)
        except AppServiceError:
            brief = _unknown_brief_row(pid)
        rows.append({"project_id": pid, "brief": brief})
    rows.sort(key=lambda row: str(row["project_id"]))
    return {
        "schema_version": 1,
        "package_id": BRIEF_PACKAGE_ID,
        "truth_boundary": BRIEF_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "briefs": rows,
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "portfolio_implicit_all": False,
            "auto_execution": False,
        },
    }


def _unknown_roadmap_row(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "available": False,
        "status": "unknown",
        "summary": None,
        "you_are_here": None,
        "next_unlock": None,
        "items": [],
        "blockers": [],
        "honesty": {
            "unknown_is_valid": True,
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "roadmap_is_canonical": False,
            "fabricated_fields": False,
            "canonical_write": False,
            "owner_capability_granted": False,
        },
    }


def _roadmap_honesty(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    honesty = {
        "unknown_is_valid": True,
        "lens_is_authority": False,
        "mcp_is_authority": False,
        "roadmap_is_canonical": False,
        "derived_status_is_authority": False,
        "ui_is_canonical": False,
        "fabricated_fields": False,
        "canonical_write": False,
        "owner_capability_granted": False,
    }
    if isinstance(payload, Mapping):
        raw = payload.get("honesty")
        if isinstance(raw, Mapping):
            for key, value in raw.items():
                if key not in honesty:
                    honesty[str(key)] = value
    return honesty


def read_vault_roadmaps(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped roadmap read. Does not materialize answers."""
    rows: list[dict[str, Any]] = []
    for project in service.projects():
        pid = str(project.get("project_id") or "").strip()
        if not pid:
            continue
        try:
            lens = service.roadmap(pid)
        except AppServiceError:
            rows.append(_unknown_roadmap_row(pid))
            continue
        rows.append(
            {
                "project_id": pid,
                "roadmap": {
                    "project_id": pid,
                    "available": bool(lens.get("available")),
                    "status": lens.get("status"),
                    "summary": lens.get("summary"),
                    "you_are_here": lens.get("you_are_here"),
                    "next_unlock": lens.get("next_unlock"),
                    "items": list(lens.get("items") or []),
                    "blockers": list(lens.get("blockers") or []),
                    "unknowns": list(lens.get("unknowns") or []),
                    "honesty": _roadmap_honesty(lens),
                },
            }
        )
    rows.sort(key=lambda row: str(row["project_id"]))
    return {
        "schema_version": 1,
        "package_id": ROADMAP_PACKAGE_ID,
        "truth_boundary": ROADMAP_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "roadmaps": rows,
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "portfolio_implicit_all": False,
            "canonical_write": False,
            "auto_execution": False,
            "owner_capability_granted": False,
            "roadmap_is_canonical": False,
        },
    }


def _compose_mission_workspace(
    service: AppService,
    *,
    lens: str,
    builder: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """Read-only mission/workspace compose. Never invents PILOT rows."""
    view = dict(builder(service.vault))
    view["authentic_pilot"] = False
    view["pilot_estate_rows"] = []
    view["ui_canonical"] = False
    view["graph_authority"] = False
    view["unknown_equals_healthy"] = False
    honesty = {
        "lens_is_authority": False,
        "mcp_is_authority": False,
        "unknown_is_valid": True,
        "fabricated_fields": False,
        "request_contains_project": False,
        "zero_arg_vault_scope": True,
        "canonical_write": False,
        "auto_execution": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "pilot_invented": False,
        "ui_is_canonical": False,
    }
    return {
        "schema_version": 1,
        "package_id": MISSION_WS_PACKAGE_ID,
        "truth_boundary": MISSION_WS_TRUTH_BOUNDARY,
        "lens": lens,
        "view": view,
        "honesty": honesty,
    }


def read_vault_mission(service: AppService) -> dict[str, Any]:
    """Zero-arg mission-control read. Does not invent PILOT estates."""
    return _compose_mission_workspace(
        service, lens="mission", builder=build_mission_view
    )


def read_vault_workspace(service: AppService) -> dict[str, Any]:
    """Zero-arg workspace read. Does not invent PILOT estates."""
    return _compose_mission_workspace(
        service, lens="workspace", builder=build_workspace_view
    )


def read_vault_graph(service: AppService) -> dict[str, Any]:
    """Zero-arg impact-graph summary. Missing graph stays UNKNOWN."""
    summary = service.graph_summary()
    available = bool(summary.get("available"))
    return {
        "schema_version": 1,
        "package_id": GRAPH_PACKAGE_ID,
        "truth_boundary": GRAPH_TRUTH_BOUNDARY,
        "graph": {
            "available": available,
            "node_count": int(summary.get("node_count") or 0),
            "edge_count": int(summary.get("edge_count") or 0),
            "graph_authority": False,
            "authority": "derived",
            "note": summary.get("note"),
            "truth_boundary": summary.get("truth_boundary"),
        },
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "graph_is_authority": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "fabricated_edges": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "canonical_write": False,
            "auto_execution": False,
            "owner_capability_granted": False,
        },
    }


def build_tool_dispatch(service: AppService) -> Mapping[str, Callable[[], dict[str, Any]]]:
    """Map allow-listed tool ids to AppService callables."""
    return {
        "atlas.ops.health.read": lambda: service.health(),
        "atlas.knowledge.query.read": lambda: {"knowledge": service.knowledge()},
        "atlas.explain.receipt.read": lambda: {
            "note": "explain receipts via snapshot graph/health only",
            "graph": service.graph_summary(),
        },
        "atlas.projects.list.read": lambda: {"projects": service.projects()},
        "atlas.brief.read": lambda: read_vault_briefs(service),
        "atlas.roadmap.read": lambda: read_vault_roadmaps(service),
        "atlas.mission.read": lambda: read_vault_mission(service),
        "atlas.workspace.read": lambda: read_vault_workspace(service),
        "atlas.graph.read": lambda: read_vault_graph(service),
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
    tid = _assert_safe_tool_id(tool_id)
    if tid not in _enabled_read_tools():
        raise McpServerError(f"mcp-tool-denied:{tid}")
    service = open_app_service(vault)
    dispatch = build_tool_dispatch(service)
    if tid not in dispatch:
        raise McpServerError(f"mcp-tool-unbound:{tid}")
    result = dispatch[tid]()
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "tool_id": tid,
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
    """Handle one JSON-line request: {\"tool\": \"...\"} -> JSON response.

    Rejects malformed JSON, non-objects, missing/empty tool, forbidden
    write/path/args keys, and unknown extra keys (AS-2.1-MCP-ADV-001).
    """
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise McpServerError(f"mcp-json-invalid:{exc}") from exc
    if not isinstance(payload, dict):
        raise McpServerError("mcp-request-not-object")
    keys = set(payload.keys())
    forbidden = sorted(keys & _FORBIDDEN_REQUEST_KEYS)
    if forbidden:
        raise McpServerError(f"mcp-request-forbidden-key:{forbidden[0]}")
    unexpected = sorted(keys - _ALLOWED_REQUEST_KEYS)
    if unexpected:
        raise McpServerError(f"mcp-request-unexpected-key:{unexpected[0]}")
    tool = payload.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise McpServerError("mcp-tool-missing")
    response = invoke_mcp_tool(vault, tool.strip(), operator=operator)
    return json.dumps(response, sort_keys=True)
