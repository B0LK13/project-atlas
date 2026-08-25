"""AS-CODER-ALPHA-DOCTOR-MCP-001 — read-only doctor projection for MCP/API/Web.

Wraps PROD-DOCTOR-001 ``run_doctor`` without writing. DOCTOR != AUTHORITY.
Unknown checks stay unknown (never healthy).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.config import AtlasConfig
from project_atlas.doctor import run_doctor, to_dict

PACKAGE_ID = "AS-CODER-ALPHA-DOCTOR-MCP-001"
CLI_PACKAGE = "PROD-DOCTOR-001"
TRUTH_BOUNDARY = (
    "DOCTOR READ != AUTHORITY / MCP != WRITE / "
    "UNKNOWN != HEALTHY / UI != CANONICAL / "
    "OPERATIONAL HEALTH != OWNER GATE"
)


class WebDoctorError(ValueError):
    """Fail-closed doctor read error."""


def _sanitize_detail(detail: str, vault: Path) -> str:
    """Do not echo host-absolute vault paths through LIVE_API / MCP."""
    resolved = str(vault.resolve())
    if resolved and resolved in detail:
        return detail.replace(resolved, "vault")
    return detail


def list_doctor(vault: Path) -> dict[str, Any]:
    """Read-only vault-scoped doctor report. Never writes. Never grants gates."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise WebDoctorError("vault is not a directory")
    report = run_doctor(AtlasConfig(), vault)
    raw = to_dict(report)
    checks: list[dict[str, Any]] = []
    raw_checks = raw.get("checks")
    if not isinstance(raw_checks, list):
        raw_checks = []
    for row in raw_checks:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        status = row.get("status")
        detail = row.get("detail")
        if not isinstance(name, str) or not name.strip():
            continue
        if status not in {"ok", "warn", "error", "unknown"}:
            status = "unknown"
        detail_text = detail if isinstance(detail, str) else "UNKNOWN"
        checks.append(
            {
                "name": name,
                "status": status,
                "detail": _sanitize_detail(detail_text, vault),
            }
        )
    rollup = raw.get("rollup")
    if rollup not in {"ok", "warn", "error", "unknown"}:
        rollup = "unknown"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "cli_package": CLI_PACKAGE,
        "truth_boundary": TRUTH_BOUNDARY,
        "rollup": rollup,
        "ok": bool(raw.get("ok")) and rollup != "error",
        "check_count": len(checks),
        "checks": checks,
        "available": bool(checks),
        "authority": False,
        "generated": {"by": "atlas-coder-alpha-doctor-mcp-001-read"},
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "ui_is_canonical": False,
            "unknown_is_valid": True,
            "unknown_equals_healthy": False,
            "fabricated_fields": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "portfolio_implicit_all": False,
            "auto_execution": False,
            "owner_gate_grant": False,
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }
