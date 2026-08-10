"""AS-2.0-KCI-001 — Knowledge Compilation Interface (thin contract).

Consume-only compile-request / compile-receipt envelopes. Never promotes
Layer B authority and never silently changes authority winners. Bound to
the Atlas 1.0 compatibility anchor (AS-2.0-COMPAT-001).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-KCI-001"
TRUTH_BOUNDARY_REQUEST = "KCI COMPILE ≠ AUTHORITY / ≠ SILENT WINNER"
TRUTH_BOUNDARY_RECEIPT = "KCI RECEIPT ≠ LAYER B AUTHORITY"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")


class KciError(ValueError):
    """Fail-closed KCI contract error."""


def _validate_id(token: str, *, label: str) -> str:
    value = token.strip()
    if not _ID_RE.fullmatch(value):
        raise KciError(f"kci-{label}-invalid")
    return value


def _validate_ref(token: str, *, label: str) -> str:
    value = token.strip()
    if not value or not _REF_RE.fullmatch(value):
        raise KciError(f"kci-{label}-invalid")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_compile_request(
    *,
    request_id: str,
    source_refs: list[str],
    output_vault: Path,
    subject_refs: list[str] | None = None,
    fixture_mode: bool = True,
    notes: str | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a deterministic consume-only KCI compile request."""
    _ = anchor or require_compatibility_anchor()
    rid = _validate_id(request_id, label="request-id")
    if not source_refs:
        raise KciError("kci-source-refs-empty")
    normalized_sources = [
        _validate_ref(item, label="source-ref") for item in source_refs
    ]
    subjects = [
        _validate_ref(item, label="subject-ref") for item in (subject_refs or [])
    ]

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "request_id": rid,
        "operation": "compile",
        "fixture_mode": fixture_mode,
        "source_refs": sorted(set(normalized_sources)),
        "authority": {
            "level": "derived",
            "note": "KCI compile request is consume-only; not Layer B authority",
        },
        "truth_boundary": TRUTH_BOUNDARY_REQUEST,
        "generated": {"by": "project-atlas"},
    }
    if subjects:
        payload["subject_refs"] = sorted(set(subjects))
    if notes:
        payload["notes"] = notes.strip()[:240]

    try:
        validate_record(payload, "kci-compile-request")
    except SchemaValidationError as exc:
        raise KciError(f"kci-request-schema:{exc}") from exc

    out = (
        output_vault.resolve()
        / "generated"
        / "kci"
        / f"{rid}-compile-request.json"
    )
    _atomic_write_json(out, payload)
    return payload


def issue_compile_receipt(
    *,
    receipt_id: str,
    request_id: str,
    output_vault: Path,
    status: Literal["accepted", "refused"] = "accepted",
    outcome_refs: list[str] | None = None,
    refusal_reason: str | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Issue a consume-only KCI compile receipt (never promotes authority)."""
    _ = anchor or require_compatibility_anchor()
    rid = _validate_id(receipt_id, label="receipt-id")
    req = _validate_id(request_id, label="request-id")
    if status == "refused" and not refusal_reason:
        raise KciError("kci-refusal-reason-required")
    if status == "accepted" and refusal_reason:
        raise KciError("kci-refusal-reason-on-accepted")

    outcomes = [
        _validate_ref(item, label="outcome-ref") for item in (outcome_refs or [])
    ]

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "request_id": req,
        "status": status,
        "consume_only": True,
        "authority_promoted": False,
        "authority": {
            "level": "derived",
            "note": "KCI receipt never promotes Layer B authority",
        },
        "truth_boundary": TRUTH_BOUNDARY_RECEIPT,
        "generated": {"by": "project-atlas"},
    }
    if outcomes:
        payload["outcome_refs"] = sorted(set(outcomes))
    if refusal_reason:
        payload["refusal_reason"] = refusal_reason.strip()[:240]

    try:
        validate_record(payload, "kci-compile-receipt")
    except SchemaValidationError as exc:
        raise KciError(f"kci-receipt-schema:{exc}") from exc

    out = (
        output_vault.resolve()
        / "generated"
        / "kci"
        / f"{rid}-compile-receipt.json"
    )
    _atomic_write_json(out, payload)
    return payload
