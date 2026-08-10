"""AS-2.0-TWIN-FIXTURE-001 — disposable twin projection fixtures.

Fixture-only Digital Twin projections for harness rehearsal. Never claims
estate PILOT PASSED or AS-2.0-TWIN-001 production READY. Authentic TWIN-001
remains BLOCKED without authentic PILOT roots.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-TWIN-FIXTURE-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

HealthState = Literal["unknown", "degraded", "healthy"]


class TwinFixtureError(ValueError):
    """Fail-closed twin fixture error."""


@dataclass(frozen=True, slots=True)
class TwinProjectRow:
    project_id: str
    display_name: str
    health: HealthState = "unknown"
    evidence_class: Literal["fixture", "absent"] = "fixture"

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "display_name": self.display_name,
            "health": self.health,
            "evidence_class": self.evidence_class,
        }


def _validate_id(token: str, *, label: str) -> str:
    value = token.strip()
    if not _ID_RE.fullmatch(value):
        raise TwinFixtureError(f"twin-fixture-{label}-invalid")
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


def build_twin_projection_fixture(
    vault: Path,
    *,
    projection_id: str,
    projects: list[TwinProjectRow] | None = None,
    authentic_pilot_roots: int = 0,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a disposable twin projection fixture (≠ TWIN production / PILOT)."""
    _ = anchor or require_compatibility_anchor()
    pid = _validate_id(projection_id, label="projection-id")
    if authentic_pilot_roots < 0:
        raise TwinFixtureError("twin-fixture-pilot-roots-invalid")

    rows = projects or []
    seen: set[str] = set()
    serialized: list[dict[str, Any]] = []
    for row in rows:
        project_id = _validate_id(row.project_id, label="project-id")
        if project_id in seen:
            raise TwinFixtureError(f"twin-fixture-project-duplicate:{project_id}")
        seen.add(project_id)
        name = row.display_name.strip()
        if not name:
            raise TwinFixtureError("twin-fixture-display-name-empty")
        # Missing authentic PILOT roots ⇒ never invent healthy estate rows.
        health: HealthState = row.health
        if authentic_pilot_roots == 0 and health == "healthy":
            health = "unknown"
        serialized.append(
            TwinProjectRow(
                project_id=project_id,
                display_name=name,
                health=health,
                evidence_class=row.evidence_class,
            ).as_dict()
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "projection_id": pid,
        "fixture_class": "disposable",
        "pilot_status": "fixture-only",
        "authentic_pilot_roots": authentic_pilot_roots,
        "estate_pilot_passed": False,
        "twin_production_ready": False,
        "twin_001_status": "BLOCKED",
        "projects": sorted(serialized, key=lambda item: item["project_id"]),
        "authority": {
            "level": "derived",
            "note": (
                "Disposable twin fixture only; AS-2.0-TWIN-001 remains BLOCKED "
                "without authentic PILOT"
            ),
        },
        "truth_boundary": (
            "TWIN FIXTURE ≠ ESTATE PILOT PASSED / ≠ TWIN PRODUCTION READY"
        ),
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "twin-projection-fixture")
    except SchemaValidationError as exc:
        raise TwinFixtureError(f"twin-fixture-schema:{exc}") from exc

    out = (
        vault.resolve()
        / "generated"
        / "ops"
        / "twin-fixtures"
        / f"{pid}.json"
    )
    _atomic_write_json(out, payload)
    return payload
