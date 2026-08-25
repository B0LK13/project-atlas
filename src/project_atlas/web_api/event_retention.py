"""AS-CODER-ALPHA-EVENT-RETENTION-READ-001 — vault-scoped REPORT READ lens.

Projects the persisted AS-INT-009 ``retention-report.json`` so humans and
agents can inspect operational retention findings. This module never
applies retention, never deletes packages/receipts, and never writes.

Honesty:
- REPORT != AUTHORITY
- RETENTION REPORT != APPLY
- LENS != TRUTH CORE
- MISSING != APPLIED
- UI / MCP / API projections are not canonical
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.event_retention import (
    REPORT_RELATIVE,
    REPORT_SCHEMA,
    RetentionError,
    read_report,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-EVENT-RETENTION-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-event-retention-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.event-retention-read.v1"
SOURCE_PACKAGE: Final[str] = "AS-INT-009"
TRUTH_BOUNDARY: Final[str] = (
    "REPORT != AUTHORITY / RETENTION REPORT != APPLY / LENS != TRUTH CORE"
)

StatusRollup = Literal["UNKNOWN", "PRESENT"]


class WebEventRetentionError(ValueError):
    """Fail-closed event-retention REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "lens_is_truth_core": False,
        "report_is_authority": False,
        "retention_report_is_apply": False,
        "missing_is_applied": False,
        "applied_status_is_live_apply": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "write_applied": False,
        "retention_applied": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebEventRetentionError(f"event-retention-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebEventRetentionError("event-retention-vault-missing")
    return root


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
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
        "report_applied": None if report is None else report.get("applied"),
        "report_dry_run": None if report is None else report.get("dry_run"),
        "report": report,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def read_event_retention(vault: Path) -> dict[str, Any]:
    """Read-only event-retention report projection. Never writes or applies."""
    root = _resolve_vault(vault)
    try:
        report = read_report(root)
    except RetentionError as exc:
        raise WebEventRetentionError(
            f"event-retention-report-unreadable:{exc}"
        ) from exc
    if report is None:
        return _envelope(
            status="UNKNOWN",
            reason=(
                "event-retention report is absent; absence is not an apply "
                "and is not project authority"
            ),
            reason_code="REPORT_ABSENT",
            available=False,
            report=None,
        )
    return _envelope(
        status="PRESENT",
        reason="persisted event-retention report is visible; REPORT != AUTHORITY",
        reason_code="REPORT_PRESENT",
        available=True,
        report=report,
    )


def render_event_retention_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    lines = [
        f"atlas retention report [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  reason:       {view.get('reason_code')}",
        f"  present:      {view.get('report_present')}",
        f"  path:         {view.get('report_path')}",
    ]
    report_status = view.get("report_status")
    if report_status is not None:
        lines.append(f"  report_status:{report_status}")
    report_applied = view.get("report_applied")
    if report_applied is not None:
        lines.append(f"  report_applied:{report_applied}")
    report_dry_run = view.get("report_dry_run")
    if report_dry_run is not None:
        lines.append(f"  report_dry_run:{report_dry_run}")
    report = view.get("report")
    if isinstance(report, dict):
        counts = report.get("counts")
        if isinstance(counts, dict):
            lines.append(
                "  counts:       "
                f"units_before={counts.get('units_before')} "
                f"units_kept={counts.get('units_kept')} "
                f"units_removed={counts.get('units_removed')}"
            )
    lines.append(
        "  honesty:      REPORT != AUTHORITY; "
        "RETENTION REPORT != APPLY; LENS != TRUTH CORE"
    )
    return "\n".join(lines) + "\n"
