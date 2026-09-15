"""AS-2.0-ESTATE-INTEL-001 — fixture-only estate intel (≠ PILOT PASS).

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

PACKAGE_ID = "AS-2.0-ESTATE-INTEL-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "ESTATE INTEL FIXTURE ≠ PILOT PASS / ≠ AUTHENTIC ROOTS"
SCHEMA_KIND = "estate-intel-fixture"


class EstateIntelFixtureError(ValueError):
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


def build_estate_intel_fixture(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic estate-intel-fixture record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise EstateIntelFixtureError("estate-intel-id-invalid")

    if int(kwargs.get("pilot_roots", 0)) != 0:
        raise EstateIntelFixtureError(
            "estate-intel-authentic-roots-forbidden-in-fixture-package"
        )
    if bool(kwargs.get("claim_pilot_passed")):
        raise EstateIntelFixtureError("estate-intel-pilot-pass-forbidden")
    rows = kwargs.get("intel_rows") or [
        {"row_id": "demo", "evidence_class": "fixture"}
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "fixture_id": rid,
        "pilot_roots": 0,
        "estate_pilot_passed": False,
        "intel_rows": list(rows),
        "authority": {
            "level": "derived",
            "note": "Fixture estate intel only; authentic PILOT still required",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise EstateIntelFixtureError(f"estate-intel-fixture-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "estate" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
