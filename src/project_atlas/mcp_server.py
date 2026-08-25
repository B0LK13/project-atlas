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
from project_atlas.ops_receipts import inventory_ops_receipts

PACKAGE_ID = "AS-2.1-MCP-SERVER-001"
ADV_PACKAGE_ID = "AS-2.1-MCP-ADV-001"
BRIEF_PACKAGE_ID = "AS-2.1-MCP-BRIEF-001"
TRUTH_BOUNDARY = "MCP_READ LIVE != WRITE / != AUTHORITY / != ESTATE SCAN"
BRIEF_TRUTH_BOUNDARY = (
    "MCP BRIEF != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)
CONFLICTS_PACKAGE_ID = "AS-CODER-ALPHA-CONFLICTS-MCP-001"
CONFLICTS_TRUTH_BOUNDARY = (
    "MCP CONFLICTS != AUTHORITY / != RESOLUTION / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)
SNAPSHOT_PACKAGE_ID = "AS-CODER-ALPHA-SNAPSHOT-MCP-001"
SNAPSHOT_TRUTH_BOUNDARY = (
    "MCP SNAPSHOT != AUTHORITY / != BACKUP BUNDLE / UNKNOWN VALID / NO WRITE / "
    "FACADE SNAPSHOT != ATLAS SNAPSHOT/RESTORE"
)
DISCOVERY_PACKAGE_ID = "AS-CODER-ALPHA-DISCOVERY-MCP-001"
DISCOVERY_TRUTH_BOUNDARY = (
    "MCP DISCOVERY != INGEST != TRUST != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "ABSENT REPORT != PILOT ROOTS"
)
RECEIPTS_PACKAGE_ID = "AS-CODER-ALPHA-OPS-RECEIPTS-MCP-001"
RECEIPTS_TRUTH_BOUNDARY = (
    "MCP OPS RECEIPTS != COMPLETION / UNKNOWN!=HEALTHY / != AUTHORITY / "
    "PRESENCE != PILOT / NO WRITE"
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


def read_vault_conflicts(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped conflict index. Does not resolve or write."""
    index = service.conflict_index()
    honesty = dict(index.get("honesty") or {})
    honesty.update(
        {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "conflict_is_resolution": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "portfolio_implicit_all": False,
            "canonical_write": False,
            "auto_execution": False,
            "owner_capability_granted": False,
            "authentic_pilot": False,
        }
    )
    return {
        "schema_version": 1,
        "package_id": CONFLICTS_PACKAGE_ID,
        "truth_boundary": CONFLICTS_TRUTH_BOUNDARY,
        "project_count": int(index.get("project_count") or 0),
        "conflict_count": int(index.get("conflict_count") or 0),
        "projects": list(index.get("projects") or []),
        "skipped_invalid_ids": int(index.get("skipped_invalid_ids") or 0),
        "authority": "derived",
        "honesty": honesty,
    }


def read_vault_snapshot(service: AppService) -> dict[str, Any]:
    """Zero-arg LIVE_API facade snapshot. Not a backup bundle."""
    raw = service.snapshot()
    projects = list(raw.get("projects") or [])
    knowledge = list(raw.get("knowledge") or [])
    graph = dict(raw.get("graph") or {})
    return {
        "schema_version": 1,
        "package_id": SNAPSHOT_PACKAGE_ID,
        "truth_boundary": SNAPSHOT_TRUTH_BOUNDARY,
        "project_count": len(projects),
        "knowledge_count": len(knowledge),
        "projects": projects,
        "knowledge": knowledge,
        "graph": {
            "available": bool(graph.get("available")),
            "node_count": int(graph.get("node_count") or 0),
            "edge_count": int(graph.get("edge_count") or 0),
            "graph_authority": False,
            "authority": "derived",
        },
        "health": raw.get("health"),
        "authority": "derived",
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
            "authentic_pilot": False,
            "backup_bundle": False,
            "atlas_snapshot_restore": False,
        },
    }


def read_vault_discovery(service: AppService) -> dict[str, Any]:
    """Zero-arg estate discovery projection. Missing report invents no roots."""
    raw = service.estate_discovery()
    categories = dict(raw.get("categories") or {})
    counts = dict(raw.get("counts") or {})
    return {
        "schema_version": 1,
        "package_id": DISCOVERY_PACKAGE_ID,
        "truth_boundary": DISCOVERY_TRUTH_BOUNDARY,
        "present": bool(raw.get("present")),
        "authorized_root": raw.get("authorized_root"),
        "volume_root_authorized": bool(raw.get("volume_root_authorized")),
        "volume_root_kind": raw.get("volume_root_kind") or "NONE",
        "counts": counts,
        "categories": categories,
        "scan": raw.get("scan"),
        "note": raw.get("note"),
        "authority": "derived",
        "honesty": {
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
            "ingest": False,
            "invented_pilot_roots": False,
        },
    }


def read_vault_ops_receipts(service: AppService) -> dict[str, Any]:
    """Zero-arg ops receipt inventory. Presence never becomes healthy."""
    raw = inventory_ops_receipts(service.vault)
    return {
        "schema_version": 1,
        "package_id": RECEIPTS_PACKAGE_ID,
        "truth_boundary": RECEIPTS_TRUTH_BOUNDARY,
        "available": bool(raw.get("available")),
        "receipt_rows": int(raw.get("receipt_rows") or 0),
        "receipts": list(raw.get("receipts") or []),
        "kinds": dict(raw.get("kinds") or {}),
        "unscanned_kinds": list(raw.get("unscanned_kinds") or []),
        "ops_root": raw.get("ops_root"),
        "rollup": "unknown",
        "health": "unknown",
        "authority": False,
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "unknown_is_valid": True,
            "unknown_equals_healthy": False,
            "fabricated_fields": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "canonical_write": False,
            "auto_execution": False,
            "owner_capability_granted": False,
            "authentic_pilot": False,
            "completion_claimed": False,
            "release_certified": False,
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
        "atlas.conflicts.read": lambda: read_vault_conflicts(service),
        "atlas.snapshot.read": lambda: read_vault_snapshot(service),
        "atlas.discovery.read": lambda: read_vault_discovery(service),
        "atlas.ops.receipts.read": lambda: read_vault_ops_receipts(service),
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
