"""AS-CODER-ALPHA-SCHEMA-COMPAT-READ-001 — vault-scoped REPORT READ lens.

Projects the persisted AS-INT-012 ``schema-compat-report.json`` so humans
and agents can inspect operational schema-compat findings. This module
never scans, never writes, and never applies a migration.

Honesty:
- REPORT != AUTHORITY
- SCHEMA-COMPAT != MIGRATION APPLY
- LENS != TRUTH CORE
- MISSING != COMPATIBLE
- UI / MCP / API projections are not canonical
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.schema_compat import (
    REPORT_RELATIVE,
    REPORT_SCHEMA,
    SchemaCompatError,
    read_report,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-SCHEMA-COMPAT-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-schema-compat-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.schema-compat-read.v1"
SOURCE_PACKAGE: Final[str] = "AS-INT-012"
TRUTH_BOUNDARY: Final[str] = (
    "REPORT != AUTHORITY / SCHEMA-COMPAT != MIGRATION APPLY / LENS != TRUTH CORE"
)

StatusRollup = Literal["UNKNOWN", "PRESENT"]


class WebSchemaCompatError(ValueError):
    """Fail-closed schema-compat REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "lens_is_truth_core": False,
        "report_is_authority": False,
        "schema_compat_is_migration_apply": False,
        "missing_is_compatible": False,
        "ok_is_migration_apply": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "write_applied": False,
        "migration_applied": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebSchemaCompatError(f"schema-compat-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebSchemaCompatError("schema-compat-vault-missing")
    return root


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_package": SOURCE_PACKAGE,
        "source_schema": REPORT_SCHEMA,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "report_present": report is not None,
        "report_path": REPORT_RELATIVE.as_posix(),
        "report_status": None if report is None else report.get("status"),
        "report_mode": None if report is None else report.get("mode"),
        "report": report,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }
    return payload


def read_schema_compat(vault: Path) -> dict[str, Any]:
    """Read-only schema-compat report projection. Never writes or migrates."""
    root = _resolve_vault(vault)
    try:
        report = read_report(root)
    except SchemaCompatError as exc:
        raise WebSchemaCompatError(f"schema-compat-report-unreadable:{exc}") from exc
    if report is None:
        return _envelope(
            status="UNKNOWN",
            reason=(
                "schema-compat report is absent; absence is not compatible "
                "and is not a migration apply"
            ),
            reason_code="REPORT_ABSENT",
            available=False,
            report=None,
        )
    return _envelope(
        status="PRESENT",
        reason="persisted schema-compat report is visible; REPORT != AUTHORITY",
        reason_code="REPORT_PRESENT",
        available=True,
        report=report,
    )


def render_schema_compat_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    lines = [
        f"atlas schema report [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  reason:       {view.get('reason_code')}",
        f"  present:      {view.get('report_present')}",
        f"  path:         {view.get('report_path')}",
    ]
    report_status = view.get("report_status")
    if report_status is not None:
        lines.append(f"  report_status:{report_status}")
    report_mode = view.get("report_mode")
    if report_mode is not None:
        lines.append(f"  report_mode:  {report_mode}")
    report = view.get("report")
    if isinstance(report, dict):
        counts = report.get("counts")
        if isinstance(counts, dict):
            lines.append(
                "  counts:       "
                f"scanned={counts.get('scanned')} "
                f"compatible={counts.get('compatible')} "
                f"missing={counts.get('missing')} "
                f"migrate_candidate={counts.get('migrate_candidate')}"
            )
    lines.append(
        "  honesty:      REPORT != AUTHORITY; "
        "SCHEMA-COMPAT != MIGRATION APPLY; LENS != TRUTH CORE"
    )
    return "\n".join(lines) + "\n"
