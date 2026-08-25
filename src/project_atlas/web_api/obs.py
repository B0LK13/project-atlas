"""AS-CODER-ALPHA-OBS-READ-001 — vault-scoped observability REPORT READ.

Wraps the existing AS-2.1-OBS-LIVE-001 live receipt
(``build_live_observability_receipt`` / GET ``/v1/obs``) as a read-only
CLI / AppService / MCP lens. This module never writes Layer B and never
persists ``generated/ops/obs/``.

Honesty:
- OBS != AUTHORITY
- LIVE_RECEIPT != CERTIFICATION
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.obs_live import (
    PACKAGE_ID as SOURCE_PACKAGE,
    build_live_observability_receipt,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-OBS-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-obs-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.obs-read.v1"
TRUTH_BOUNDARY: Final[str] = (
    "OBS != AUTHORITY / LIVE_RECEIPT != CERTIFICATION / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY"
)
TOOL_ID: Final[str] = "atlas.obs.read"

# Optional ops markers only. Module-available flags stay True on an
# empty vault and must not be treated as health evidence.
_OPTIONAL_SURFACES: Final[tuple[str, ...]] = (
    "web_actions",
    "chatgpt_bridge",
    "collab",
    "provider_live",
    "scheduler",
    "autonomy_l3",
    "oai_responses_poc",
    "authz_audit",
    "pilot_prep",
    "perf_baselines",
    "ask_atlas_ops",
    "sync_plan_dry_run",
    "sync_ops",
    "query_ops",
)

class WebObsError(ValueError):
    """Fail-closed observability REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "obs_is_authority": False,
        "live_receipt_is_certification": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "ui_is_canonical": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebObsError(f"obs-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebObsError("obs-vault-missing")
    return root


def _optional_marker_count(surfaces: dict[str, Any]) -> int:
    return sum(1 for key in _OPTIONAL_SURFACES if bool(surfaces.get(key)))


def read_obs(vault: Path) -> dict[str, Any]:
    """Read-only live observability projection. Never writes."""
    root = _resolve_vault(vault)
    receipt = build_live_observability_receipt(
        root, receipt_id="obs-read", write=False
    )
    surfaces = receipt.get("surfaces")
    surface_map = surfaces if isinstance(surfaces, dict) else {}
    optional_count = _optional_marker_count(surface_map)
    empty = optional_count == 0
    reason_code = "EMPTY_RECEIPT" if empty else "LIVE_RECEIPT_UNKNOWN"
    reason = (
        "no optional ops markers; empty is not healthy and is not authority"
        if empty
        else (
            "live observability receipt is visible; UNKNOWN rollup is not "
            "healthy and is not certification"
        )
    )
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_package": SOURCE_PACKAGE,
        "tool_id": TOOL_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": True,
        "status": "UNKNOWN",
        "healthy": False,
        "empty": empty,
        "reason": reason,
        "reason_code": reason_code,
        "optional_marker_count": optional_count,
        "receipt_rollup": receipt.get("rollup"),
        "receipt": receipt,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_obs_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent health."""
    lines = [
        f"atlas ops obs [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  healthy:      {view.get('healthy')}",
        f"  empty:        {view.get('empty')}",
        f"  reason:       {view.get('reason_code')}",
        f"  rollup:       {view.get('receipt_rollup')}",
        f"  markers:      {view.get('optional_marker_count')}",
        (
            "  honesty:      OBS != AUTHORITY; LIVE_RECEIPT != CERTIFICATION; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; MCP != AUTHORITY; "
            "WRITE_APPLIED=false"
        ),
    ]
    return "\n".join(lines) + "\n"
