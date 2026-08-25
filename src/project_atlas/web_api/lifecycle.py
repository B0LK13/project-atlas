"""AS-CODER-ALPHA-LIFECYCLE-READ-001 -- vault-scoped lifecycle REPORT READ.

Inspects the persisted AS-CORE2-010 fixture lifecycle-certify report at
``generated/ops/lifecycle-cert-report.json``. This module never runs the
lifecycle matrix, never writes a certify report, and never promotes
Layer B authority.

Honesty:
- LIFECYCLE != AUTHORITY
- CERTIFY_REPORT != PILOT PASS
- MISSING != CERTIFIED
- EMPTY != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-LIFECYCLE-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-lifecycle-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.lifecycle-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-CORE2-010",)
TRUTH_BOUNDARY: Final[str] = (
    "LIFECYCLE != AUTHORITY / CERTIFY_REPORT != PILOT PASS / "
    "MISSING != CERTIFIED / EMPTY != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

OPS_REL: Final[Path] = Path("generated") / "ops"
REPORT_REL: Final[Path] = OPS_REL / "lifecycle-cert-report.json"

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "LIFECYCLE != AUTHORITY",
    "CERTIFY_REPORT != PILOT PASS",
    "MISSING != CERTIFIED",
    "EMPTY != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

ProjectionStatus = Literal["MISSING", "EMPTY", "PRESENT"]
StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebLifecycleError(ValueError):
    """Fail-closed lifecycle REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lifecycle_is_authority": False,
        "certify_report_is_pilot_pass": False,
        "missing_is_certified": False,
        "missing_is_healthy": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "certify_executed": False,
        "report_written": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "estate_pilot_passed": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebLifecycleError(f"lifecycle-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebLifecycleError("lifecycle-vault-missing")
    return root


def _inside(vault: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise WebLifecycleError(f"lifecycle-path-unreadable:{exc}") from exc
    if not resolved.is_relative_to(vault):
        raise WebLifecycleError("lifecycle-path-escape")
    return resolved


def _projection_root(
    vault: Path, relative: Path
) -> tuple[ProjectionStatus, Path | None]:
    raw = vault / relative
    if not raw.exists():
        return "MISSING", None
    if raw.is_symlink() or not raw.is_dir():
        raise WebLifecycleError(
            f"lifecycle-projection-not-directory:{relative.as_posix()}"
        )
    return "EMPTY", _inside(vault, raw)


def _read_json_object(vault: Path, path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WebLifecycleError(f"lifecycle-not-regular-file:{path.name}")
    resolved = _inside(vault, path)
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WebLifecycleError(f"lifecycle-malformed-json:{path.name}") from exc
    except OSError as exc:
        raise WebLifecycleError(f"lifecycle-unreadable:{path.name}") from exc
    if not isinstance(loaded, dict):
        raise WebLifecycleError(f"lifecycle-json-not-object:{path.name}")
    return loaded


def _validate(payload: dict[str, Any], schema_kind: str, name: str) -> None:
    try:
        validate_record(payload, schema_kind)
    except SchemaValidationError as exc:
        raise WebLifecycleError(f"lifecycle-malformed-record:{name}") from exc


def _case_ids(payload: dict[str, Any]) -> list[str]:
    raw_cases = payload.get("cases")
    cases = raw_cases if isinstance(raw_cases, list) else []
    ids = [
        str(item.get("case_id"))
        for item in cases
        if isinstance(item, dict) and item.get("case_id") is not None
    ]
    ids.sort(key=str.casefold)
    return ids


def _case_records(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_cases = payload.get("cases")
    cases = raw_cases if isinstance(raw_cases, list) else []
    rows: list[dict[str, str]] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = item.get("case_id")
        result = item.get("result")
        if case_id is None or result is None:
            continue
        rows.append({"case_id": str(case_id), "result": str(result)})
    rows.sort(key=lambda row: row["case_id"].casefold())
    return rows


def _counts(payload: dict[str, Any] | None) -> dict[str, int] | None:
    if payload is None:
        return None
    raw = payload.get("counts")
    if not isinstance(raw, dict):
        return None
    return {
        "total": int(raw.get("total", 0)),
        "passed": int(raw.get("passed", 0)),
        "failed": int(raw.get("failed", 0)),
    }


def _inspect_report(
    vault: Path,
) -> tuple[ProjectionStatus, dict[str, Any] | None]:
    _, ops_root = _projection_root(vault, OPS_REL)
    if ops_root is None:
        return "MISSING", None
    raw = vault / REPORT_REL
    if not raw.exists():
        return "EMPTY", None
    payload = _read_json_object(vault, raw)
    _validate(payload, "lifecycle-cert-report", raw.name)
    if payload.get("estate_pilot_passed") is not False:
        raise WebLifecycleError("lifecycle-pilot-pass-claimed")
    return "PRESENT", payload


def _rollup(
    report_status: ProjectionStatus,
) -> tuple[StatusRollup, str, str, bool]:
    if report_status == "PRESENT":
        return (
            "PRESENT",
            "persisted lifecycle certify report is visible; "
            "LIFECYCLE != AUTHORITY; CERTIFY_REPORT != PILOT PASS",
            "ARTIFACTS_PRESENT",
            True,
        )
    if report_status == "MISSING":
        return (
            "UNKNOWN",
            "lifecycle certify report is absent; absence is not CERTIFIED "
            "and is not healthy",
            "ARTIFACTS_ABSENT",
            False,
        )
    return (
        "EMPTY",
        "generated/ops exists but holds no lifecycle certify report; "
        "EMPTY != HEALTHY",
        "ARTIFACTS_EMPTY",
        False,
    )


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    report_status: ProjectionStatus,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    counts = _counts(payload)
    case_ids = _case_ids(payload) if payload is not None else []
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "artifacts": {
            "certify_report": {
                "status": report_status,
                "path": REPORT_REL.as_posix(),
                "report_status": (
                    payload.get("status") if payload is not None else None
                ),
                "estate_pilot_passed": False,
                "package": payload.get("package") if payload is not None else None,
                "counts": counts,
                "case_ids": case_ids,
                "case_count": len(case_ids),
                "records": _case_records(payload) if payload is not None else [],
            }
        },
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_lifecycle(vault: Path) -> dict[str, Any]:
    """Read-only lifecycle certify-report inspect. Never certifies or writes."""
    root = _resolve_vault(vault)
    report_status, payload = _inspect_report(root)
    status, reason, reason_code, available = _rollup(report_status)
    return _envelope(
        status=status,
        reason=reason,
        reason_code=reason_code,
        available=available,
        report_status=report_status,
        payload=payload,
    )


def render_lifecycle_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    artifacts = view.get("artifacts")
    report: dict[str, Any] = {}
    if isinstance(artifacts, dict):
        raw_report = artifacts.get("certify_report")
        if isinstance(raw_report, dict):
            report = raw_report
    report_status = report.get("report_status")
    lines = [
        f"atlas lifecycle report [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  reason:       {view.get('reason_code')}",
        (
            "  report:       "
            f"{report.get('status', 'MISSING')} "
            f"cases={report.get('case_count', 0)}"
            + (
                f" report_status={report_status}"
                if report_status is not None
                else ""
            )
        ),
        "  estate_pilot_passed: false",
        (
            "  honesty:      LIFECYCLE != AUTHORITY; "
            "CERTIFY_REPORT != PILOT PASS; MISSING != CERTIFIED; "
            "EMPTY != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
