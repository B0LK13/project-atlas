"""AS-2.0-SYNC-001 - production sync plan under final-cert fixture waiver.

Unlocked by AS-2.0-FINAL-CERT-PILOT-WAIVER. Never claims authentic estate PILOT.
Uses fixture evidence_class only while AUTHENTIC_ESTATE_PILOT=NO.
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

PACKAGE_ID = "AS-2.0-SYNC-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = (
    "SYNC-001 PRODUCTION != AUTHENTIC ESTATE PILOT / "
    "FIXTURE-ONLY UNDER OWNER FINAL-CERT WAIVER"
)


class SyncProductionError(ValueError):
    """Fail-closed SYNC-001 production error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_sync_production_plan(
    vault: Path,
    *,
    plan_id: str,
    projects: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a production sync plan under the final-cert fixture waiver."""
    require_compatibility_anchor()
    require_final_cert_pilot_waiver()
    pid = plan_id.strip()
    if not _ID_RE.fullmatch(pid):
        raise SyncProductionError("sync-plan-id-invalid")
    rows = projects or [
        {
            "project_id": "fixture-alpha",
            "disposition": "eligible",
            "evidence_class": "fixture",
        }
    ]
    for row in rows:
        if row.get("evidence_class") != "fixture":
            raise SyncProductionError("sync-evidence-class-must-be-fixture")
        if row.get("disposition") not in {"eligible", "quarantined", "disabled"}:
            raise SyncProductionError("sync-disposition-invalid")
    flags = waiver_flags()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "plan_id": pid,
        "pilot_mode": flags["pilot_mode"],
        "authentic_estate_pilot": False,
        "owner_waived": True,
        "honest_label": HONEST_LABEL,
        "production": True,
        "projects": rows,
        "authority": {
            "level": "derived",
            "note": "SYNC-001 production under fixture final-cert waiver only",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "sync-production-plan")
    except SchemaValidationError as exc:
        raise SyncProductionError(f"sync-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "sync" / f"{pid}-production-plan.json"
    _atomic_write_json(out, payload)
    return payload
