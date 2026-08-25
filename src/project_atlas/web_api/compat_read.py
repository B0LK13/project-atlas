"""AS-CODER-ALPHA-COMPAT-READ-001 -- vault-scoped compatibility-anchor REPORT READ.

Read-only wrap of the existing AS-2.0-COMPAT-001 pin loader
(``load_compatibility_anchor``). This module never writes vault state,
never wakes Atlas-OPT, and never treats the 1.0 pin as current GA,
Truth Core, or merge authority.

Honesty:
- COMPAT != AUTHORITY
- ANCHOR != TRUTH CORE
- CERTIFIED != GA
- AUTHENTIC_PILOT_FIELD != CURRENT PILOT
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatAnchorError,
    load_compatibility_anchor,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-COMPAT-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-compat-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.compat-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.0-COMPAT-001",)
SOURCE_COMMAND: Final[str] = "atlas compat verify"
TRUTH_BOUNDARY: Final[str] = (
    "COMPAT != AUTHORITY / ANCHOR != TRUTH CORE / CERTIFIED != GA / "
    "AUTHENTIC_PILOT_FIELD != CURRENT PILOT / EMPTY != HEALTHY / "
    "UNKNOWN != HEALTHY / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "D149_TOUCHED = NO / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "COMPAT != AUTHORITY",
    "ANCHOR != TRUTH CORE",
    "CERTIFIED != GA",
    "AUTHENTIC_PILOT_FIELD != CURRENT PILOT",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebCompatReadError(ValueError):
    """Fail-closed compatibility-anchor REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "compat_is_authority": False,
        "anchor_is_truth_core": False,
        "certified_is_ga": False,
        "authentic_pilot_field_is_current": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "compat_state_written": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "owner_capability_granted": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "graph_is_authority": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebCompatReadError(f"compat-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebCompatReadError("compat-read-vault-missing")
    return root


def _existing_anchor() -> dict[str, Any]:
    """Call the existing AS-2.0-COMPAT-001 loader. Never writes."""
    try:
        anchor = load_compatibility_anchor()
    except CompatAnchorError as exc:
        raise WebCompatReadError(f"compat-read-anchor-unreadable:{exc}") from exc
    except OSError as exc:
        raise WebCompatReadError(f"compat-read-anchor-unreadable:{exc}") from exc
    payload = anchor.as_dict()
    if not isinstance(payload, dict):
        raise WebCompatReadError("compat-read-anchor-invalid")
    return payload


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    snapshot = str(view.get("snapshot_id") or "")
    if snapshot != SNAPSHOT_ID:
        return (
            "UNKNOWN",
            "existing compatibility anchor snapshot is unread or unexpected; "
            "UNKNOWN != HEALTHY; COMPAT != AUTHORITY; ANCHOR != TRUTH CORE",
            "UNKNOWN_COMPAT_ANCHOR",
            False,
        )
    return (
        "PRESENT",
        "existing AS-2.0-COMPAT-001 pin loaded; COMPAT != AUTHORITY; "
        "ANCHOR != TRUTH CORE; CERTIFIED != GA",
        "COMPAT_ANCHOR_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_command": SOURCE_COMMAND,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "view": view,
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_compat_view(vault: Path) -> dict[str, Any]:
    """Read-only wrap of atlas compat verify. Never writes vault state."""
    _resolve_vault(vault)
    view = _existing_anchor()
    return _envelope(view=view)


def render_compat_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas compat report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  source_command:   {view.get('source_command', SOURCE_COMMAND)}",
        f"  snapshot_id:      {inner.get('snapshot_id', 'UNKNOWN')}",
        f"  freeze_head:      {inner.get('software_freeze_head', 'UNKNOWN')}",
        f"  freeze_tree:      {inner.get('software_freeze_tree', 'UNKNOWN')}",
        f"  release_certified:{inner.get('release_certified', 'UNKNOWN')}",
        (
            "  honesty:          COMPAT != AUTHORITY; ANCHOR != TRUTH CORE; "
            "CERTIFIED != GA; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
