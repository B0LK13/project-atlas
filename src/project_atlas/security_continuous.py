"""AS-2.0-SEC-001 — continuous security scan receipt (metadata only).

Bound to the Atlas 1.0 compatibility anchor. Never Layer B authority.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-SEC-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "SEC RECEIPT ≠ MATCHED CONTENT LOG / ≠ AUTHORITY"
SCHEMA_KIND = "security-continuous-receipt"


class SecurityContinuousError(ValueError):
    """Fail-closed contract error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_security_continuous_receipt(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic security-continuous-receipt record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise SecurityContinuousError("sec-receipt-id-invalid")

    findings = int(kwargs.get("findings_count", 0))
    if findings < 0:
        raise SecurityContinuousError("sec-findings-invalid")
    status = "clean" if findings == 0 else "findings"
    if bool(kwargs.get("log_matched_content")):
        raise SecurityContinuousError("sec-matched-content-log-forbidden")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "findings_count": findings,
        "matched_content_logged": False,
        "status": status,
        "authority": {
            "level": "derived",
            "note": "Security receipts return metadata only; never matched secrets",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise SecurityContinuousError(f"security-continuous-receipt-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "security" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
