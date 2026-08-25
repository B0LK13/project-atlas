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
from project_atlas.overview import OverviewError, build_overview_lens
from project_atlas.project_changed import (
    INVENTORY_RELATIVE,
    PREV_INVENTORY_RELATIVE,
    ProjectChangedError,
    build_changed_lens,
    diff_inventories,
)
from project_atlas.project_decisions import ProjectDecisionsError, build_decisions_lens
from project_atlas.project_unknown import ProjectUnknownError, build_unknown_lens

PACKAGE_ID = "AS-2.1-MCP-SERVER-001"
ADV_PACKAGE_ID = "AS-2.1-MCP-ADV-001"
BRIEF_PACKAGE_ID = "AS-2.1-MCP-BRIEF-001"
OVERVIEW_PACKAGE_ID = "AS-CODER-ALPHA-OVERVIEW-MCP-001"
DECISIONS_PACKAGE_ID = "AS-CODER-ALPHA-DECISIONS-MCP-001"
UNKNOWN_PACKAGE_ID = "AS-CODER-ALPHA-UNKNOWN-MCP-001"
CHANGED_PACKAGE_ID = "AS-CODER-ALPHA-CHANGED-MCP-001"
LENS_PACKAGE_ID = "AS-CODER-ALPHA-LENS-MCP-001"
TRUTH_BOUNDARY = "MCP_READ LIVE != WRITE / != AUTHORITY / != ESTATE SCAN"
BRIEF_TRUTH_BOUNDARY = (
    "MCP BRIEF != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)
LENS_TRUTH_BOUNDARY = (
    "MCP LENS != AUTHORITY / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL / NO INVENTORY ROTATE"
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


def _vault_project_ids(service: AppService) -> list[str]:
    ids: list[str] = []
    for project in service.projects():
        pid = str(project.get("project_id") or "").strip()
        if pid:
            ids.append(pid)
    return ids


def _lens_honesty() -> dict[str, Any]:
    return {
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
    }


def _unknown_lens_row(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "available": False,
        "status": "unknown",
        "summary": None,
        "value": None,
        "honesty": {
            "unknown_is_valid": True,
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "fabricated_fields": False,
        },
    }


def _overlay_honesty(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    honesty = {
        "unknown_is_valid": True,
        "lens_is_authority": False,
        "mcp_is_authority": False,
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


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def read_vault_overviews(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped overview read. Does not materialize answers."""
    rows: list[dict[str, Any]] = []
    for pid in _vault_project_ids(service):
        try:
            lens = build_overview_lens(service.vault, pid)
            rows.append(
                {
                    "project_id": pid,
                    "overview": {
                        "project_id": pid,
                        "available": True,
                        "status": lens.get("status"),
                        "summary": lens.get("summary"),
                        "value": lens.get("value"),
                        "coverage": lens.get("coverage") or {},
                        "notes": list(lens.get("notes") or []),
                        "honesty": _overlay_honesty(lens),
                    },
                }
            )
        except (OverviewError, AppServiceError, OSError):
            rows.append({"project_id": pid, "overview": _unknown_lens_row(pid)})
    rows.sort(key=lambda row: str(row["project_id"]))
    return {
        "schema_version": 1,
        "package_id": OVERVIEW_PACKAGE_ID,
        "family_package_id": LENS_PACKAGE_ID,
        "truth_boundary": LENS_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "overviews": rows,
        "honesty": _lens_honesty(),
    }


def read_vault_decisions(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped decisions read. Never promotes or writes."""
    rows: list[dict[str, Any]] = []
    for pid in _vault_project_ids(service):
        try:
            lens = build_decisions_lens(service.vault, pid)
            rows.append(
                {
                    "project_id": pid,
                    "decisions": {
                        "project_id": pid,
                        "available": True,
                        "status": lens.get("status"),
                        "summary": lens.get("summary"),
                        "value": lens.get("value"),
                        "decision_count": int(lens.get("decision_count") or 0),
                        "active_governing_count": int(
                            lens.get("active_governing_count") or 0
                        ),
                        "decisions": list(lens.get("decisions") or []),
                        "honesty": _overlay_honesty(lens),
                    },
                }
            )
        except (ProjectDecisionsError, AppServiceError, OSError):
            rows.append({"project_id": pid, "decisions": _unknown_lens_row(pid)})
    rows.sort(key=lambda row: str(row["project_id"]))
    return {
        "schema_version": 1,
        "package_id": DECISIONS_PACKAGE_ID,
        "family_package_id": LENS_PACKAGE_ID,
        "truth_boundary": LENS_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "projects": rows,
        "honesty": _lens_honesty(),
    }


def read_vault_unknowns(service: AppService) -> dict[str, Any]:
    """Zero-arg vault-scoped unknown/conflict read. Never resolves."""
    rows: list[dict[str, Any]] = []
    for pid in _vault_project_ids(service):
        try:
            lens = build_unknown_lens(service.vault, pid)
            rows.append(
                {
                    "project_id": pid,
                    "unknown": {
                        "project_id": pid,
                        "available": True,
                        "status": lens.get("status"),
                        "rollup": lens.get("rollup"),
                        "summary": lens.get("summary"),
                        "value": lens.get("value"),
                        "signals": lens.get("signals") or {},
                        "honesty": _overlay_honesty(lens),
                    },
                }
            )
        except (ProjectUnknownError, AppServiceError, OSError):
            rows.append({"project_id": pid, "unknown": _unknown_lens_row(pid)})
    rows.sort(key=lambda row: str(row["project_id"]))
    return {
        "schema_version": 1,
        "package_id": UNKNOWN_PACKAGE_ID,
        "family_package_id": LENS_PACKAGE_ID,
        "truth_boundary": LENS_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "projects": rows,
        "honesty": _lens_honesty(),
    }


def read_vault_changed(service: AppService) -> dict[str, Any]:
    """Zero-arg what-changed read. Never rotates inventory or writes answers."""
    current = _read_json_object(service.vault / INVENTORY_RELATIVE)
    previous = _read_json_object(service.vault / PREV_INVENTORY_RELATIVE)
    rows: list[dict[str, Any]] = []
    for pid in _vault_project_ids(service):
        if current is None:
            row = _unknown_lens_row(pid)
            row["rollup"] = "baseline"
            row["delta"] = {
                "added_count": 0,
                "removed_count": 0,
                "modified_count": 0,
                "prior_baseline": False,
            }
            rows.append({"project_id": pid, "changed": row})
            continue
        try:
            delta = diff_inventories(previous, current)
            lens = build_changed_lens(
                service.vault,
                pid,
                previous=previous,
                current=current,
                delta=delta,
            )
            raw_delta = lens.get("delta")
            lens_delta: dict[str, Any] = (
                raw_delta if isinstance(raw_delta, dict) else {}
            )
            rows.append(
                {
                    "project_id": pid,
                    "changed": {
                        "project_id": pid,
                        "available": True,
                        "status": lens.get("status"),
                        "rollup": lens.get("rollup"),
                        "summary": lens.get("summary"),
                        "value": lens.get("value"),
                        "delta": {
                            "added_count": int(lens_delta.get("added_count") or 0),
                            "removed_count": int(lens_delta.get("removed_count") or 0),
                            "modified_count": int(lens_delta.get("modified_count") or 0),
                            "prior_baseline": bool(delta.get("prior_baseline")),
                            "added": list(lens_delta.get("added") or []),
                            "removed": list(lens_delta.get("removed") or []),
                            "modified": list(lens_delta.get("modified") or []),
                        },
                        "honesty": _overlay_honesty(lens),
                    },
                }
            )
        except (ProjectChangedError, AppServiceError, OSError):
            rows.append({"project_id": pid, "changed": _unknown_lens_row(pid)})
    rows.sort(key=lambda row: str(row["project_id"]))
    return {
        "schema_version": 1,
        "package_id": CHANGED_PACKAGE_ID,
        "family_package_id": LENS_PACKAGE_ID,
        "truth_boundary": LENS_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "projects": rows,
        "honesty": _lens_honesty(),
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
        "atlas.overview.read": lambda: read_vault_overviews(service),
        "atlas.decisions.read": lambda: read_vault_decisions(service),
        "atlas.unknown.read": lambda: read_vault_unknowns(service),
        "atlas.changed.read": lambda: read_vault_changed(service),
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
