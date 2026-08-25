"""AS-CODER-ALPHA-OPT-GATE-READ-001 -- vault-scoped opt-gate REPORT READ.

Read-only wrap of the existing AS-OPT-GATE-001 sealed policy surface
(``load_opt_gate_policies`` + ``ATLAS_OPT_WAKE_GATE``). This module never
runs an experiment, never seals a new envelope, never wakes Atlas-OPT,
and never treats PROMOTE_ELIGIBLE as merge, deploy, or authority.

Honesty:
- OPT-GATE != OPT
- OPT-GATE != AUTOLAB
- PROMOTE_ELIGIBLE != MERGED
- PROMOTE_ELIGIBLE != DEPLOYED
- PROMOTE_ELIGIBLE != AUTHORITATIVE
- WAKE_GATE = CLOSED
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

from project_atlas.opt_gate import (
    ATLAS_OPT_WAKE_GATE,
    POLICY_REL,
    OptGateError,
    load_opt_gate_policies,
)
from project_atlas.opt_gate import (
    PACKAGE_ID as OPT_GATE_PACKAGE_ID,
)
from project_atlas.opt_gate import (
    TRUTH_BOUNDARY as OPT_GATE_TRUTH_BOUNDARY,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-OPT-GATE-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-opt-gate-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.opt-gate-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-OPT-GATE-001",)
SOURCE_SURFACE: Final[str] = "load_opt_gate_policies"
TRUTH_BOUNDARY: Final[str] = (
    "OPT-GATE != OPT / OPT-GATE != AUTOLAB / PROMOTE_ELIGIBLE != MERGED / "
    "PROMOTE_ELIGIBLE != DEPLOYED / PROMOTE_ELIGIBLE != AUTHORITATIVE / "
    "WAKE_GATE = CLOSED / EMPTY != HEALTHY / UNKNOWN != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "OPT-GATE != OPT",
    "OPT-GATE != AUTOLAB",
    "PROMOTE_ELIGIBLE != MERGED",
    "PROMOTE_ELIGIBLE != DEPLOYED",
    "PROMOTE_ELIGIBLE != AUTHORITATIVE",
    "WAKE_GATE = CLOSED",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebOptGateReadError(ValueError):
    """Fail-closed opt-gate REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "opt_gate_is_opt": False,
        "opt_gate_is_autolab": False,
        "promote_eligible_is_merged": False,
        "promote_eligible_is_deployed": False,
        "promote_eligible_is_authoritative": False,
        "wake_gate": ATLAS_OPT_WAKE_GATE,
        "atlas_opt_wake_gate": ATLAS_OPT_WAKE_GATE,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "opt_gate_state_written": False,
        "experiment_run": False,
        "envelope_sealed": False,
        "opt_woken": False,
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
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebOptGateReadError(f"opt-gate-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebOptGateReadError("opt-gate-read-vault-missing")
    return root


def _repo_root() -> Path:
    # src/project_atlas/web_api/opt_gate_read.py -> repository root
    return Path(__file__).resolve().parents[3]


def _existing_policies() -> dict[str, Any]:
    """Load sealed policies. Never runs or seals an experiment."""
    policy_root = (_repo_root() / POLICY_REL).resolve()
    if not policy_root.is_dir():
        raise WebOptGateReadError("opt-gate-read-policies-missing")
    try:
        policies = load_opt_gate_policies(policy_root)
    except OptGateError as exc:
        raise WebOptGateReadError(f"opt-gate-read-policies-unreadable:{exc.code}") from exc
    except OSError as exc:
        raise WebOptGateReadError(f"opt-gate-read-policies-unreadable:{exc}") from exc
    scoring = dict(policies.scoring)
    hard_gates = dict(policies.hard_gates)
    return {
        "schema_version": 1,
        "package_id": OPT_GATE_PACKAGE_ID,
        "truth_boundary": OPT_GATE_TRUTH_BOUNDARY,
        "wake_gate": ATLAS_OPT_WAKE_GATE,
        "policy_root": POLICY_REL.as_posix(),
        "scoring_caller_supplied_scores_accepted": scoring.get(
            "caller_supplied_scores_accepted"
        ),
        "scoring_subjective_scores_accepted": scoring.get("subjective_scores_accepted"),
        "hard_gate_names": sorted(str(name) for name in hard_gates),
        "threshold_keys": sorted(str(name) for name in policies.thresholds),
        "honesty_catalog_present": bool(policies.honesty_catalog),
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    if view.get("wake_gate") != "CLOSED":
        return (
            "UNKNOWN",
            "opt-gate wake flag is unread or unexpected; UNKNOWN != HEALTHY; "
            "OPT-GATE != OPT; WAKE_GATE = CLOSED is required",
            "UNKNOWN_OPT_GATE",
            False,
        )
    if view.get("package_id") != OPT_GATE_PACKAGE_ID:
        return (
            "UNKNOWN",
            "opt-gate policy package is unread or unexpected; UNKNOWN != HEALTHY",
            "UNKNOWN_OPT_GATE",
            False,
        )
    return (
        "PRESENT",
        "existing AS-OPT-GATE-001 sealed policies loaded; OPT-GATE != OPT; "
        "PROMOTE_ELIGIBLE != MERGED; WAKE_GATE = CLOSED",
        "OPT_GATE_POLICIES_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_surface": SOURCE_SURFACE,
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


def read_opt_gate_view(vault: Path) -> dict[str, Any]:
    """Read-only wrap of AS-OPT-GATE-001 policies. Never writes or wakes OPT."""
    _resolve_vault(vault)
    view = _existing_policies()
    return _envelope(view=view)


def render_opt_gate_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas opt-gate report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  source_surface:   {view.get('source_surface', SOURCE_SURFACE)}",
        f"  wake_gate:        {inner.get('wake_gate', 'UNKNOWN')}",
        f"  policy_root:      {inner.get('policy_root', 'UNKNOWN')}",
        (
            "  honesty:          OPT-GATE != OPT; PROMOTE_ELIGIBLE != MERGED; "
            "WAKE_GATE = CLOSED; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
