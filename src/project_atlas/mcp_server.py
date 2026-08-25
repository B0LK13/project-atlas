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

PACKAGE_ID = "AS-2.1-MCP-SERVER-001"
ADV_PACKAGE_ID = "AS-2.1-MCP-ADV-001"
BRIEF_PACKAGE_ID = "AS-2.1-MCP-BRIEF-001"
STATE_ATTENTION_PACKAGE_ID = "AS-CODER-ALPHA-MCP-STATE-ATTENTION-001"
ROADMAP_PACKAGE_ID = "AS-CODER-ALPHA-MCP-ROADMAP-001"
TRUTH_BOUNDARY = "MCP_READ LIVE != WRITE / != AUTHORITY / != ESTATE SCAN"
BRIEF_TRUTH_BOUNDARY = (
    "MCP BRIEF != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)
STATE_ATTENTION_TRUTH_BOUNDARY = (
    "MCP STATE/ATTENTION != AUTHORITY / UNKNOWN VALID / RISK != FACT / "
    "NO WRITE / VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
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


def _lens_honesty() -> dict[str, Any]:
    return {
        "lens_is_authority": False,
        "mcp_is_authority": False,
        "unknown_is_valid": True,
        "fabricated_fields": False,
        "request_contains_project": False,
        "zero_arg_vault_scope": True,
        "portfolio_implicit_all": False,
        "auto_execution": False,
        "risk_is_fact": False,
        "empty_is_not_health_grade": True,
    }


def _unknown_state_row(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "available": False,
        "honesty": "NO_DATA",
        "authority_note": "derived-state-not-canonical",
        "known_facts": [],
        "unknown_facts": [],
        "stale_facts": [],
        "contested_facts": [],
        "attention_candidates": [],
        "honesty_flags": {
            "unknown_is_valid": True,
            "lens_is_authority": False,
            "fabricated_fields": False,
        },
    }


def _unknown_attention_row(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "available": False,
        "honesty": "NO_DATA",
        "authority_note": "risk-is-not-fact",
        "risks": [],
        "attention_rank_is_score": "NO",
        "numeric_priority_score": None,
        "honesty_flags": {
            "unknown_is_valid": True,
            "lens_is_authority": False,
            "fabricated_fields": False,
            "risk_is_fact": False,
        },
    }


def _iter_project_ids(service: AppService) -> list[str]:
    ids: list[str] = []
    for project in service.projects():
        pid = str(project.get("project_id") or "").strip()
        if pid:
            ids.append(pid)
    return sorted(ids)


def read_vault_project_states(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped project-state read. Does not invent projects or write."""
    rows: list[dict[str, Any]] = []
    for pid in _iter_project_ids(service):
        try:
            state = service.project_state(pid)
        except AppServiceError:
            state = _unknown_state_row(pid)
        rows.append({"project_id": pid, "state": state})
    return {
        "schema_version": 1,
        "package_id": STATE_ATTENTION_PACKAGE_ID,
        "truth_boundary": STATE_ATTENTION_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "states": rows,
        "honesty": _lens_honesty(),
    }


def read_vault_project_attentions(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped attention read. Risk is not fact. No writes."""
    rows: list[dict[str, Any]] = []
    for pid in _iter_project_ids(service):
        try:
            attention = service.project_attention(pid)
        except AppServiceError:
            attention = _unknown_attention_row(pid)
        rows.append({"project_id": pid, "attention": attention})
    return {
        "schema_version": 1,
        "package_id": STATE_ATTENTION_PACKAGE_ID,
        "truth_boundary": STATE_ATTENTION_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "attentions": rows,
        "honesty": _lens_honesty(),
    }


def _unknown_roadmap_row(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "available": False,
        "status": "unknown",
        "items": [],
        "blockers": [],
        "unknowns": ["roadmap-unavailable"],
        "honesty": {
            "unknown_is_valid": True,
            "lens_is_authority": False,
            "roadmap_is_canonical": False,
            "ui_is_canonical": False,
            "fabricated_fields": False,
        },
    }


def read_vault_roadmaps(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped roadmap read. ROADMAP != canonical. No writes."""
    rows: list[dict[str, Any]] = []
    for pid in _iter_project_ids(service):
        try:
            roadmap = service.roadmap(pid)
        except AppServiceError:
            roadmap = _unknown_roadmap_row(pid)
        rows.append({"project_id": pid, "roadmap": roadmap})
    return {
        "schema_version": 1,
        "package_id": ROADMAP_PACKAGE_ID,
        "truth_boundary": STATE_ATTENTION_TRUTH_BOUNDARY + " / ROADMAP != CANONICAL",
        "project_count": len(rows),
        "roadmaps": rows,
        "honesty": {
            **_lens_honesty(),
            "roadmap_is_canonical": False,
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
        "atlas.project-state.read": lambda: read_vault_project_states(service),
        "atlas.project-attention.read": lambda: read_vault_project_attentions(service),
        "atlas.roadmap.read": lambda: read_vault_roadmaps(service),
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
