"""AS-2.0-MCP-001 — deny-by-default MCP tool registry (no live server).

Contract freeze for MCP/tool classes. Does not start a server, does not
wire production OpenAI/MCP SDKs. Bound to Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-MCP-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9.-]{0,127}$")
ToolClass = Literal[
    "vault-read", "vault-write", "estate-scan", "provider-generate"
]
TRUTH_BOUNDARY = "MCP REGISTRY ≠ LIVE SERVER / ≠ AUTHORITY / ≠ ESTATE SCAN"


class McpRegistryError(ValueError):
    """Fail-closed MCP registry error."""


@dataclass(frozen=True, slots=True)
class McpTool:
    tool_id: str
    tool_class: ToolClass
    enabled: bool
    reason: str


DEFAULT_TOOLS: tuple[McpTool, ...] = (
    McpTool(
        "atlas.ops.health.read",
        "vault-read",
        True,
        "allow-list candidate; read-only ops health",
    ),
    McpTool(
        "atlas.knowledge.query.read",
        "vault-read",
        True,
        "allow-list candidate; knowledge query read",
    ),
    McpTool(
        "atlas.explain.receipt.read",
        "vault-read",
        True,
        "allow-list candidate; explain receipts",
    ),
    McpTool(
        "atlas.projects.list.read",
        "vault-read",
        True,
        "allow-list candidate; project inventory read",
    ),
    McpTool(
        "atlas.brief.read",
        "vault-read",
        True,
        "allow-list candidate; Coder Alpha project briefs (vault-scoped, read-only)",
    ),
    McpTool(
        "atlas.project-state.read",
        "vault-read",
        True,
        "allow-list candidate; Coder Alpha project-state (vault-scoped, read-only)",
    ),
    McpTool(
        "atlas.project-attention.read",
        "vault-read",
        True,
        "allow-list candidate; Coder Alpha project-attention (vault-scoped, read-only)",
    ),
    McpTool(
        "atlas.roadmap.read",
        "vault-read",
        True,
        "allow-list candidate; Coder Alpha living roadmap (vault-scoped, read-only)",
    ),
    McpTool(
        "atlas.vault.write",
        "vault-write",
        False,
        "deny-by-default; protected paths",
    ),
    McpTool(
        "atlas.estate.scan",
        "estate-scan",
        False,
        "deny until authentic PILOT roots",
    ),
    McpTool(
        "atlas.provider.generate",
        "provider-generate",
        False,
        "quarantine lane only; no live SDK in this package",
    ),
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_mcp_tool_registry(
    vault: Path,
    *,
    registry_id: str,
    tools: list[McpTool] | None = None,
    enable_live_server: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a deny-by-default MCP tool registry without starting a server."""
    _ = anchor or require_compatibility_anchor()
    if enable_live_server:
        raise McpRegistryError(
            "mcp-live-server-forbidden:AS-2.0-MCP-001-contract-freeze-only"
        )
    rid = registry_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise McpRegistryError("mcp-registry-id-invalid")

    rows = list(tools) if tools is not None else list(DEFAULT_TOOLS)
    if not rows:
        raise McpRegistryError("mcp-tools-empty")
    serialized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in rows:
        tid = tool.tool_id.strip()
        if not _ID_RE.fullmatch(tid):
            raise McpRegistryError(f"mcp-tool-id-invalid:{tid}")
        if tid in seen:
            raise McpRegistryError(f"mcp-tool-duplicate:{tid}")
        seen.add(tid)
        # Hard denies cannot be enabled in this package.
        if tool.tool_class in {"vault-write", "estate-scan"} and tool.enabled:
            raise McpRegistryError(
                f"mcp-tool-enable-forbidden:{tool.tool_class}"
            )
        reason = tool.reason.strip()
        if not reason:
            raise McpRegistryError("mcp-tool-reason-empty")
        serialized.append(
            {
                "tool_id": tid,
                "class": tool.tool_class,
                "enabled": bool(tool.enabled),
                "reason": reason,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "registry_id": rid,
        "live_server": False,
        "default_policy": "deny",
        "tools": serialized,
        "authority": {
            "level": "derived",
            "note": "MCP registry is contract-only; no live server wiring",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "mcp-tool-registry")
    except SchemaValidationError as exc:
        raise McpRegistryError(f"mcp-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "mcp" / f"{rid}-tool-registry.json"
    _atomic_write_json(out, payload)
    return payload
