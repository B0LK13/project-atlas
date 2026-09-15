"""AS-2.0-TWIN-001 - Digital Twin production under final-cert fixture waiver.

twin_production_ready=true under FIXTURE_ONLY_OWNER_WAIVER, while
estate_pilot_passed / authentic_estate_pilot remain false forever unless
authentic roots exist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.final_cert_pilot import (
    HONEST_LABEL,
    require_final_cert_pilot_waiver,
    waiver_flags,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-TWIN-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = (
    "TWIN-001 PRODUCTION READY UNDER FIXTURE FINAL-CERT WAIVER != "
    "AUTHENTIC ESTATE PILOT PASSED"
)


class TwinProductionError(ValueError):
    """Fail-closed TWIN-001 production error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_twin_production_projection(
    vault: Path,
    *,
    projection_id: str,
    projects: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a production twin projection under the final-cert fixture waiver."""
    require_compatibility_anchor()
    require_final_cert_pilot_waiver()
    pid = projection_id.strip()
    if not _ID_RE.fullmatch(pid):
        raise TwinProductionError("twin-projection-id-invalid")
    rows = projects or [
        {
            "project_id": "fixture-alpha",
            "display_name": "Fixture Alpha",
            "health": "unknown",
            "evidence_class": "fixture",
        }
    ]
    for row in rows:
        if row.get("evidence_class") != "fixture":
            raise TwinProductionError("twin-evidence-class-must-be-fixture")
        if row.get("health") not in {"unknown", "degraded", "healthy"}:
            raise TwinProductionError("twin-health-invalid")
    flags = waiver_flags()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "projection_id": pid,
        "pilot_mode": flags["pilot_mode"],
        "authentic_estate_pilot": False,
        "owner_waived": True,
        "honest_label": HONEST_LABEL,
        "twin_production_ready": True,
        "estate_pilot_passed": False,
        "projects": rows,
        "authority": {
            "level": "derived",
            "note": "TWIN-001 production unlocked under fixture final-cert waiver",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "twin-production-projection")
    except SchemaValidationError as exc:
        raise TwinProductionError(f"twin-schema-invalid:{exc}") from exc
    out = (
        vault
        / "generated"
        / "ops"
        / "twin"
        / f"{pid}-production-projection.json"
    )
    _atomic_write_json(out, payload)
    return payload
