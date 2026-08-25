"""AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001 — vault-scoped skip-receipt lens.

Reads existing ``generated/ops/incremental-connect-receipt.json`` so humans
and agents can inspect the last operational reconnect decision without
re-evaluating skip, writing, or inventing authority.

Honesty:
- missing receipt stays UNKNOWN (never HEALTHY / FRESH / SKIP)
- recorded ``no_change_skip`` is operational history, not validate or Truth Core
- this lens never writes, never grants owner capability, never runs connect
- UI / MCP / API projections are not canonical
- a demo fixture must not masquerade as an authentic skip
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas import incremental_connect as incremental_connect_mod

INCREMENTAL_RECEIPT_RELATIVE = incremental_connect_mod.INCREMENTAL_RECEIPT_RELATIVE
INCREMENTAL_PACKAGE_ID = incremental_connect_mod.PACKAGE_ID
INCREMENTAL_SCHEMA_ID = incremental_connect_mod.SCHEMA_ID

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-incremental-connect-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.incremental-connect-read.v1"
TRUTH_BOUNDARY: Final[str] = (
    "INCREMENTAL SKIP != AUTHORITY / ABSENT != SKIP / SKIP != VALIDATE"
)
_KNOWN_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "full_compile",
        "no_change_skip",
        "dirty_prior_full_recompile",
        "unknown_full_compile",
    }
)
_REQUIRED_RECEIPT_KEYS: Final[tuple[str, ...]] = (
    "schema",
    "package",
    "disposition",
    "reason",
)

StatusRollup = Literal["UNKNOWN", "RECORDED"]


class IncrementalConnectReadError(ValueError):
    """Fail-closed incremental-connect read error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "incremental_skip_is_authority": False,
        "incremental_skip_is_validate": False,
        "incremental_skip_is_operational": True,
        "absent_is_skip": False,
        "unknown_is_healthy": False,
        "unknown_is_fresh": False,
        "receipt_is_live_certification": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "fabricated_skip": False,
        "connect_applied": False,
        "write_applied": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _empty_counters() -> dict[str, int]:
    return {
        "files_inspected": 0,
        "content_changed": 0,
        "semantic_records_changed": 0,
        "physical_writes": 0,
        "projections_regenerated": 0,
        "ingest_invocations": 0,
        "discover_invocations": 0,
    }


def build_incremental_connect_read(vault: Path) -> dict[str, Any]:
    """Read-only incremental-connect receipt projection. Never writes."""
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise IncrementalConnectReadError(
            f"incremental-connect-vault-unreadable:{exc}"
        ) from exc
    if not root.is_dir():
        raise IncrementalConnectReadError("incremental-connect-vault-missing")

    receipt_path = root / INCREMENTAL_RECEIPT_RELATIVE
    receipt_present = receipt_path.is_file()
    if not receipt_present:
        return {
            "schema_version": 1,
            "schema": SCHEMA_ID,
            "package_id": PACKAGE_ID,
            "truth_boundary": TRUTH_BOUNDARY,
            "available": False,
            "status": "UNKNOWN",
            "disposition": "unknown",
            "reason": (
                "No incremental-connect receipt on disk; absence is not a "
                "no-change skip and is not HEALTHY."
            ),
            "reason_code": "RECEIPT_ABSENT",
            "receipt_present": False,
            "receipt_path": INCREMENTAL_RECEIPT_RELATIVE.as_posix(),
            "source_package": INCREMENTAL_PACKAGE_ID,
            "counters": _empty_counters(),
            "delta": {},
            "honesty": _honesty(),
            "generated": {"by": GENERATOR_ID},
        }

    try:
        raw = receipt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IncrementalConnectReadError(
            f"incremental-connect-receipt-unreadable:{exc}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IncrementalConnectReadError(
            "malformed incremental-connect receipt"
        ) from exc
    if not isinstance(payload, dict):
        raise IncrementalConnectReadError("malformed incremental-connect receipt")
    for key in _REQUIRED_RECEIPT_KEYS:
        if key not in payload:
            raise IncrementalConnectReadError(
                f"incremental-connect-receipt-missing-{key}"
            )
    if payload.get("schema") != INCREMENTAL_SCHEMA_ID:
        raise IncrementalConnectReadError("incremental-connect-receipt-schema-mismatch")
    if payload.get("package") != INCREMENTAL_PACKAGE_ID:
        raise IncrementalConnectReadError("incremental-connect-receipt-package-mismatch")
    disposition = payload.get("disposition")
    if not isinstance(disposition, str) or disposition not in _KNOWN_DISPOSITIONS:
        raise IncrementalConnectReadError("incremental-connect-receipt-disposition-invalid")

    counters = {
        key: int(payload[key]) if isinstance(payload.get(key), int) else 0
        for key in _empty_counters()
    }
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    reason = payload.get("reason")
    reason_text = reason if isinstance(reason, str) and reason.strip() else "recorded"
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": True,
        "status": "RECORDED",
        "disposition": disposition,
        "reason": (
            "Incremental-connect receipt is recorded operational history; "
            "no_change_skip is not validate, owner capability, or AUTHENTIC_PILOT."
        ),
        "reason_code": "RECEIPT_RECORDED",
        "receipt_present": True,
        "receipt_path": INCREMENTAL_RECEIPT_RELATIVE.as_posix(),
        "source_package": INCREMENTAL_PACKAGE_ID,
        "source_reason": reason_text,
        "fingerprint_digest": payload.get("fingerprint_digest"),
        "prior_receipt_complete": payload.get("prior_receipt_complete"),
        "counters": counters,
        "delta": delta,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_incremental_connect_read_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    raw_counters = report.get("counters")
    counters: dict[str, Any] = raw_counters if isinstance(raw_counters, dict) else {}
    lines = [
        f"atlas incremental-connect [{report.get('status', 'UNKNOWN')}]",
        f"  available:    {report.get('available')}",
        f"  disposition:  {report.get('disposition', 'unknown')}",
        f"  reason:       {report.get('reason_code')}",
        f"  receipt:      {report.get('receipt_present')}",
        f"  inspected:    {counters.get('files_inspected', 0)}",
        f"  ingest:       {counters.get('ingest_invocations', 0)}",
        f"  discover:     {counters.get('discover_invocations', 0)}",
        "  honesty:      INCREMENTAL SKIP != AUTHORITY; "
        "ABSENT != SKIP; SKIP != VALIDATE",
    ]
    return "\n".join(lines) + "\n"
