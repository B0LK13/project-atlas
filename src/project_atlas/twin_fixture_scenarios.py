"""AS-2.0-TWIN-FIXTURE-002 — Digital Twin fixture scenario deepen (≠ production).

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

PACKAGE_ID = "AS-2.0-TWIN-FIXTURE-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "TWIN FIXTURE SCENARIO ≠ PILOT PASS / ≠ TWIN PRODUCTION READY"
SCHEMA_KIND = "twin-fixture-scenario"


class TwinFixtureScenarioError(ValueError):
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


def build_twin_fixture_scenario(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic twin-fixture-scenario record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise TwinFixtureScenarioError("twin-scenario-id-invalid")

    if bool(kwargs.get("claim_production_ready")):
        raise TwinFixtureScenarioError("twin-production-ready-forbidden")
    steps = kwargs.get("steps") or [
        {"step_id": "project", "action": "project-fixture", "evidence_class": "fixture"},
        {"step_id": "health", "action": "health-unknown", "evidence_class": "fixture"},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "scenario_id": rid,
        "estate_pilot_passed": False,
        "twin_production_ready": False,
        "steps": list(steps),
        "authority": {
            "level": "derived",
            "note": "Twin fixture scenarios only; TWIN-001 production BLOCKED",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise TwinFixtureScenarioError(f"twin-fixture-scenario-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "twin" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
