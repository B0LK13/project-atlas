"""AS-2.0-REALITY-GAP-001 fixture inventory tests."""

from __future__ import annotations

from pathlib import Path

from project_atlas.reality_gap import (
    CANONICAL_GAPS,
    build_reality_gap_inventory,
)
from project_atlas.schema import available_schemas, validate_record

ROOT = Path(__file__).resolve().parents[2]


def test_reality_gap_inventory_canonical(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_reality_gap_inventory(vault)
    assert report["pilot_roots"] == 0
    assert report["scenario_count"] == len(CANONICAL_GAPS)
    assert report["compat_snapshot_id"] == "atlas-1.0.0-compat"
    assert all(s["evidence_class"] == "fixture-only" for s in report["scenarios"])
    assert all(s["invent_pilot_roots"] is False for s in report["scenarios"])
    assert all(s["authentic_estate"] is False for s in report["scenarios"])
    validate_record(report, "reality-gap-inventory")
    assert (vault / "generated" / "ops" / "reality-gap-inventory.json").is_file()


def test_reality_gap_fixture_files_exist() -> None:
    fixture_dir = ROOT / "docs" / "atlas-2.0" / "fixtures" / "reality-gap"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "inventory.fixture.json").is_file()
    assert (ROOT / "docs" / "AS-2.0-REALITY-GAP-001.md").is_file()
    assert "reality-gap-inventory" in available_schemas()


def test_reality_gap_doc_lists_canonical_ids() -> None:
    text = (ROOT / "docs" / "atlas-2.0" / "REALITY-GAP.md").read_text(encoding="utf-8")
    for gap_id in (
        "estate-twin",
        "agent-os-in-core",
        "federation",
        "advanced-ux",
        "production-sync",
        "provider-mcp",
    ):
        assert gap_id in text
