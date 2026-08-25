"""AS-CODER-ALPHA-KCI-READ-001 -- vault-scoped Knowledge CI REPORT READ.

Inspects persisted AS-2.0-KCI-001 compile requests/receipts under
``generated/kci/`` and AS-2.0-KCI-HARNESS-001 records under
``generated/ops/kci/``. This module never issues a compile request,
never writes a receipt, never runs the Knowledge CI harness, and never
promotes Layer B authority.

Honesty:
- KCI != AUTHORITY
- RECEIPT != CERTIFICATION
- EMPTY != HEALTHY
- MISSING != PASS
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-KCI-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-kci-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.kci-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = (
    "AS-2.0-KCI-001",
    "AS-2.0-KCI-HARNESS-001",
)
TRUTH_BOUNDARY: Final[str] = (
    "KCI != AUTHORITY / RECEIPT != CERTIFICATION / EMPTY != HEALTHY / "
    "MISSING != PASS / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "D149_TOUCHED = NO / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)

ENVELOPE_REL: Final[Path] = Path("generated") / "kci"
HARNESS_REL: Final[Path] = Path("generated") / "ops" / "kci"
REQUEST_SUFFIX: Final[str] = "-compile-request.json"
RECEIPT_SUFFIX: Final[str] = "-compile-receipt.json"

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "KCI != AUTHORITY",
    "RECEIPT != CERTIFICATION",
    "EMPTY != HEALTHY",
    "MISSING != PASS",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

ProjectionStatus = Literal["MISSING", "EMPTY", "PRESENT"]
StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebKciError(ValueError):
    """Fail-closed Knowledge CI REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "kci_is_authority": False,
        "receipt_is_certification": False,
        "empty_is_healthy": False,
        "missing_is_pass": False,
        "missing_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "harness_executed": False,
        "request_issued": False,
        "receipt_issued": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebKciError(f"kci-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebKciError("kci-vault-missing")
    return root


def _inside(vault: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise WebKciError(f"kci-path-unreadable:{exc}") from exc
    if not resolved.is_relative_to(vault):
        raise WebKciError("kci-path-escape")
    return resolved


def _projection_root(
    vault: Path, relative: Path
) -> tuple[ProjectionStatus, Path | None]:
    raw = vault / relative
    if not raw.exists():
        return "MISSING", None
    if raw.is_symlink() or not raw.is_dir():
        raise WebKciError(f"kci-projection-not-directory:{relative.as_posix()}")
    return "EMPTY", _inside(vault, raw)


def _read_json_object(vault: Path, path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WebKciError(f"kci-not-regular-file:{path.name}")
    resolved = _inside(vault, path)
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WebKciError(f"kci-malformed-json:{path.name}") from exc
    except OSError as exc:
        raise WebKciError(f"kci-unreadable:{path.name}") from exc
    if not isinstance(loaded, dict):
        raise WebKciError(f"kci-json-not-object:{path.name}")
    return loaded


def _relative_posix(vault: Path, path: Path) -> str:
    return _inside(vault, path).relative_to(vault).as_posix()


def _request_summary(vault: Path, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "compile-request",
        "path": _relative_posix(vault, path),
        "request_id": str(payload["request_id"]),
        "operation": payload.get("operation"),
        "fixture_mode": payload.get("fixture_mode"),
    }


def _receipt_summary(vault: Path, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "compile-receipt",
        "path": _relative_posix(vault, path),
        "receipt_id": str(payload["receipt_id"]),
        "request_id": str(payload["request_id"]),
        "status": payload.get("status"),
        "authority_promoted": payload.get("authority_promoted"),
        "consume_only": payload.get("consume_only"),
    }


def _harness_summary(vault: Path, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    raw_gates = payload.get("gates")
    gates = raw_gates if isinstance(raw_gates, list) else []
    gate_ids = [
        str(item.get("gate_id"))
        for item in gates
        if isinstance(item, dict) and item.get("gate_id") is not None
    ]
    gate_ids.sort(key=str.casefold)
    return {
        "kind": "harness-record",
        "path": _relative_posix(vault, path),
        "harness_id": str(payload["harness_id"]),
        "authority_promoted": payload.get("authority_promoted"),
        "gate_count": len(gates),
        "gate_ids": gate_ids,
    }


def _validate(payload: dict[str, Any], schema_kind: str, name: str) -> None:
    try:
        validate_record(payload, schema_kind)
    except SchemaValidationError as exc:
        raise WebKciError(f"kci-malformed-record:{name}") from exc


def _list_envelopes(
    vault: Path,
) -> tuple[
    ProjectionStatus,
    ProjectionStatus,
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    _, root = _projection_root(vault, ENVELOPE_REL)
    if root is None:
        return "MISSING", "MISSING", [], []
    requests: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.name.endswith(".json"):
            continue
        if path.name.endswith(REQUEST_SUFFIX):
            payload = _read_json_object(vault, path)
            _validate(payload, "kci-compile-request", path.name)
            requests.append(_request_summary(vault, path, payload))
        elif path.name.endswith(RECEIPT_SUFFIX):
            payload = _read_json_object(vault, path)
            _validate(payload, "kci-compile-receipt", path.name)
            receipts.append(_receipt_summary(vault, path, payload))
    request_status: ProjectionStatus = "PRESENT" if requests else "EMPTY"
    receipt_status: ProjectionStatus = "PRESENT" if receipts else "EMPTY"
    return request_status, receipt_status, requests, receipts


def _list_harness(
    vault: Path,
) -> tuple[ProjectionStatus, list[dict[str, Any]]]:
    _, root = _projection_root(vault, HARNESS_REL)
    if root is None:
        return "MISSING", []
    records: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.name.endswith(".json"):
            continue
        payload = _read_json_object(vault, path)
        _validate(payload, "knowledge-ci-harness", path.name)
        records.append(_harness_summary(vault, path, payload))
    if records:
        return "PRESENT", records
    return "EMPTY", []


def _ids(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = [str(item[key]) for item in rows if key in item]
    values.sort(key=str.casefold)
    return values


def _rollup(
    requests: ProjectionStatus,
    receipts: ProjectionStatus,
    harness: ProjectionStatus,
) -> tuple[StatusRollup, str, str, bool]:
    states = (requests, receipts, harness)
    if any(state == "PRESENT" for state in states):
        return (
            "PRESENT",
            "persisted kci receipts/reports are visible; KCI != AUTHORITY",
            "ARTIFACTS_PRESENT",
            True,
        )
    if all(state == "MISSING" for state in states):
        return (
            "UNKNOWN",
            "kci receipts/reports are absent; absence is not PASS and is not healthy",
            "ARTIFACTS_ABSENT",
            False,
        )
    return (
        "EMPTY",
        "kci directories exist but hold no receipts/reports; EMPTY != HEALTHY",
        "ARTIFACTS_EMPTY",
        False,
    )


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    request_status: ProjectionStatus,
    requests: list[dict[str, Any]],
    receipt_status: ProjectionStatus,
    receipts: list[dict[str, Any]],
    harness_status: ProjectionStatus,
    harness: list[dict[str, Any]],
) -> dict[str, Any]:
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
            "compile_requests": {
                "status": request_status,
                "path": ENVELOPE_REL.as_posix(),
                "count": len(requests),
                "request_ids": _ids(requests, "request_id"),
                "records": requests,
            },
            "compile_receipts": {
                "status": receipt_status,
                "path": ENVELOPE_REL.as_posix(),
                "count": len(receipts),
                "receipt_ids": _ids(receipts, "receipt_id"),
                "records": receipts,
            },
            "harness_records": {
                "status": harness_status,
                "path": HARNESS_REL.as_posix(),
                "count": len(harness),
                "harness_ids": _ids(harness, "harness_id"),
                "records": harness,
            },
        },
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_kci(vault: Path) -> dict[str, Any]:
    """Read-only KCI receipt/report inspect. Never writes or runs the harness."""
    root = _resolve_vault(vault)
    request_status, receipt_status, requests, receipts = _list_envelopes(root)
    harness_status, harness = _list_harness(root)
    status, reason, reason_code, available = _rollup(
        request_status, receipt_status, harness_status
    )
    return _envelope(
        status=status,
        reason=reason,
        reason_code=reason_code,
        available=available,
        request_status=request_status,
        requests=requests,
        receipt_status=receipt_status,
        receipts=receipts,
        harness_status=harness_status,
        harness=harness,
    )


def render_kci_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    artifacts = view.get("artifacts")
    requests: dict[str, Any] = {}
    receipts: dict[str, Any] = {}
    harness: dict[str, Any] = {}
    if isinstance(artifacts, dict):
        raw_requests = artifacts.get("compile_requests")
        raw_receipts = artifacts.get("compile_receipts")
        raw_harness = artifacts.get("harness_records")
        if isinstance(raw_requests, dict):
            requests = raw_requests
        if isinstance(raw_receipts, dict):
            receipts = raw_receipts
        if isinstance(raw_harness, dict):
            harness = raw_harness
    lines = [
        f"atlas kci report [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  reason:       {view.get('reason_code')}",
        (
            "  requests:     "
            f"{requests.get('status', 'MISSING')} "
            f"count={requests.get('count', 0)}"
        ),
        (
            "  receipts:     "
            f"{receipts.get('status', 'MISSING')} "
            f"count={receipts.get('count', 0)}"
        ),
        (
            "  harness:      "
            f"{harness.get('status', 'MISSING')} "
            f"count={harness.get('count', 0)}"
        ),
        (
            "  honesty:      KCI != AUTHORITY; RECEIPT != CERTIFICATION; "
            "EMPTY != HEALTHY; MISSING != PASS; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
