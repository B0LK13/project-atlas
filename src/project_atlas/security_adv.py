"""AS-2.0-SEC-ADV-001 — advanced security control matrix (metadata only).

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

PACKAGE_ID = "AS-2.0-SEC-ADV-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "SEC ADV MATRIX ≠ MATCHED CONTENT LOG / ≠ AUTHORITY"
SCHEMA_KIND = "security-adv-matrix"


class SecurityAdvError(ValueError):
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


def build_security_adv_matrix(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic security-adv-matrix record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise SecurityAdvError("sec-adv-id-invalid")

    if bool(kwargs.get("log_matched_content")):
        raise SecurityAdvError("sec-adv-matched-content-log-forbidden")
    controls = kwargs.get("controls") or [
        {"control_id": "secrets-scan", "family": "secrets", "status": "present"},
        {"control_id": "path-safety", "family": "path-safety", "status": "present"},
        {"control_id": "quarantine", "family": "quarantine", "status": "present"},
        {"control_id": "receipt-gate", "family": "receipt", "status": "partial"},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "matrix_id": rid,
        "matched_content_logged": False,
        "controls": list(controls),
        "authority": {
            "level": "derived",
            "note": "ADV security matrix is metadata-only control inventory",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise SecurityAdvError(f"security-adv-matrix-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "security" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
