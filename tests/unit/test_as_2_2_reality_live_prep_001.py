"""AS-2.2-REALITY-LIVE-001 PREP — fixture / design gate (no production mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
LANE = ROOT / "docs" / "atlas-2.2" / "reality-live"
CONTRACTS = ROOT / "docs" / "atlas-2.2" / "contracts" / "reality-live"
FIXTURES = LANE / "fixtures"

REQUIRED_PLANES = (
    "conversational",
    "documentary",
    "implementation",
    "operational",
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_prep_docs_exist() -> None:
    assert (ROOT / "docs" / "AS-2.2-REALITY-LIVE-001.md").is_file()
    assert (LANE / "README.md").is_file()
    assert (LANE / "COLLECTORS-DESIGN.md").is_file()
    assert (LANE / "PLANES.md").is_file()
    assert (FIXTURES / "README.md").is_file()
    assert (CONTRACTS / "README.md").is_file()


def test_planes_fixture_lists_four_planes() -> None:
    planes_path = FIXTURES / "planes.fixture.json"
    schema_path = CONTRACTS / "reality-live-planes.schema.draft.json"
    payload = _load_json(planes_path)
    schema = _load_json(schema_path)
    assert isinstance(payload, dict)
    assert isinstance(schema, dict)
    jsonschema.validate(instance=payload, schema=schema)

    assert payload["package_id"] == "AS-2.2-REALITY-LIVE-001"
    assert payload["phase"] == "prep"
    assert payload["evidence_class"] == "fixture-only"
    assert payload["pilot_roots"] == 0
    assert payload["invent_pilot_roots"] is False
    assert payload["authentic_estate_pilot_passed"] is False
    assert payload["plane_count"] == 4
    assert "generated.at" not in payload.get("generated", {})

    plane_ids = [p["plane_id"] for p in payload["planes"]]
    assert tuple(plane_ids) == REQUIRED_PLANES
    assert all(p["can_certify_live_production_alone"] is False for p in payload["planes"])


def test_collectors_fixture_matches_gap_report_draft() -> None:
    collectors_path = FIXTURES / "collectors.fixture.json"
    schema_path = CONTRACTS / "reality-live-gap-report.schema.draft.json"
    payload = _load_json(collectors_path)
    schema = _load_json(schema_path)
    assert isinstance(payload, dict)
    assert isinstance(schema, dict)
    jsonschema.validate(instance=payload, schema=schema)

    assert payload["package_id"] == "AS-2.2-REALITY-LIVE-001"
    assert payload["evidence_class"] == "fixture-only"
    assert payload["pilot_roots"] == 0
    assert payload["invent_pilot_roots"] is False
    assert payload["authority"]["level"] == "derived"
    assert payload["plane_report_count"] == 4
    assert payload["gap_count"] == len(payload["gaps"])
    assert "generated.at" not in payload.get("generated", {})

    report_planes = [r["plane_id"] for r in payload["plane_reports"]]
    assert set(report_planes) == set(REQUIRED_PLANES)
    assert all(r["invent_pilot_roots"] is False for r in payload["plane_reports"])
    assert all(r["authentic_estate"] is False for r in payload["plane_reports"])


def test_design_docs_name_all_planes() -> None:
    planes_doc = (LANE / "PLANES.md").read_text(encoding="utf-8")
    design_doc = (LANE / "COLLECTORS-DESIGN.md").read_text(encoding="utf-8")
    for plane_id in REQUIRED_PLANES:
        assert plane_id in planes_doc
        assert plane_id in design_doc


def test_prep_does_not_ship_production_schema_yet() -> None:
    """Draft schemas stay under docs/; production schema registry unchanged in PREP."""
    from project_atlas.schema import available_schemas

    names = available_schemas()
    assert "reality-live-planes" not in names
    assert "reality-live-gap-report" not in names
    # Predecessor remains.
    assert "reality-gap-inventory" in names
