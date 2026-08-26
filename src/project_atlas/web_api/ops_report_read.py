"""AS-CODER-ALPHA-OPS-REPORT-READ-001 -- vault-scoped ops-report REPORT READ.

Read-only consume of persisted AS-OBS-003 ops-report artifacts under
generated/ops/ops-report.*. This module never invokes the ops-report
emitter, never writes, and never treats the report as authority.

Honesty:
- OPS REPORT != AUTHORITY
- HEALTH SNAPSHOT != THIS SURFACE
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-OPS-REPORT-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-ops-report-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.ops-report-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-OBS-003",)
SOURCE_RELATIVES: Final[tuple[str, ...]] = (
    "generated/ops/ops-report.json",
    "generated/ops/ops-report.md",
)
SOURCE_COMMAND: Final[str] = "atlas ops-report-status"
TRUTH_BOUNDARY: Final[str] = (
    "OPS REPORT != AUTHORITY / HEALTH SNAPSHOT != THIS SURFACE / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "OPS REPORT != AUTHORITY",
    "HEALTH SNAPSHOT != THIS SURFACE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebOpsReportReadError(ValueError):
    """Fail-closed ops-report REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "ops_report_is_authority": False,
        "health_snapshot_invoked": False,
        "emit_invoked": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebOpsReportReadError(f"ops-report-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebOpsReportReadError("ops-report-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebOpsReportReadError("ops-report-read-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebOpsReportReadError("ops-report-read-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebOpsReportReadError("ops-report-read-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebOpsReportReadError(f"ops-report-read-merge-authority-invented:{name}")
    if payload.get("ops_report_is_authority") is True:
        raise WebOpsReportReadError("ops-report-read-authority-invented")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebOpsReportReadError(f"ops-report-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebOpsReportReadError(f"ops-report-read-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _existing_report(vault: Path) -> dict[str, Any]:
    json_path = vault / "generated" / "ops" / "ops-report.json"
    md_path = vault / "generated" / "ops" / "ops-report.md"
    json_present = json_path.exists()
    md_present = md_path.exists()
    if json_present:
        if json_path.is_symlink():
            raise WebOpsReportReadError("ops-report-read-symlink-forbidden")
        if not json_path.is_file():
            raise WebOpsReportReadError("ops-report-read-artifact-not-file")
        _inside(vault, json_path)
    if md_present:
        if md_path.is_symlink():
            raise WebOpsReportReadError("ops-report-read-symlink-forbidden")
        if not md_path.is_file():
            raise WebOpsReportReadError("ops-report-read-md-not-file")
        _inside(vault, md_path)

    record: dict[str, Any] | None = None
    malformed = 0
    if json_present:
        try:
            record = _load_json_object(_inside(vault, json_path))
        except WebOpsReportReadError as exc:
            if "invented" in str(exc) or "symlink" in str(exc) or "escape" in str(exc):
                raise
            malformed += 1
            record = None

    return {
        "schema_version": 1,
        "json_present": json_present,
        "markdown_present": md_present,
        "malformed_count": malformed,
        "record": record,
        "json_relative": "generated/ops/ops-report.json",
        "markdown_relative": "generated/ops/ops-report.md",
        "emit_invoked": False,
        "health_snapshot_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    json_present = bool(view.get("json_present"))
    malformed = view.get("malformed_count")
    malformed_count = malformed if isinstance(malformed, int) else 0
    record = view.get("record")
    if not json_present and not view.get("markdown_present"):
        return (
            "EMPTY",
            "no existing ops-report artifacts; EMPTY != HEALTHY; OPS REPORT != AUTHORITY",
            "EMPTY_OPS_REPORT_VIEW",
            False,
        )
    if malformed_count > 0 or (json_present and not isinstance(record, dict)):
        return (
            "UNKNOWN",
            "ops-report artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy report",
            "UNKNOWN_OPS_REPORT_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing ops-report projected; OPS REPORT != AUTHORITY",
        "OPS_REPORT_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_relatives": list(SOURCE_RELATIVES),
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


def read_ops_report_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing ops-report artifacts. Never writes."""
    return _envelope(view=_existing_report(_resolve_vault(vault)))


def render_ops_report_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    record = inner.get("record") if isinstance(inner.get("record"), dict) else {}
    rollup = ""
    if isinstance(record, dict):
        raw_rollup = record.get("rollup")
        if isinstance(raw_rollup, dict):
            rollup = _ascii_token(raw_rollup.get("estate") or raw_rollup.get("status") or "")
        elif raw_rollup is not None:
            rollup = _ascii_token(raw_rollup)
    lines = [
        f"atlas ops-report-status [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  json_present:     {inner.get('json_present', False)}",
        f"  markdown_present: {inner.get('markdown_present', False)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        f"  estate_rollup:    {rollup or '(none)'}",
        (
            "  honesty:          OPS REPORT != AUTHORITY; EMPTY != HEALTHY; "
            "UNKNOWN != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
