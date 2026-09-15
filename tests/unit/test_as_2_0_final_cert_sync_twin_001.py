"""Final-cert waiver + SYNC-001 / TWIN-001 production tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.final_cert_pilot import (
    HONEST_LABEL,
    WAIVER_MODE,
    require_final_cert_pilot_waiver,
)
from project_atlas.schema import available_schemas, validate_record
from project_atlas.sync_production import (
    SyncProductionError,
    build_sync_production_plan,
)
from project_atlas.twin_production import build_twin_production_projection


def test_waiver_pin_loaded() -> None:
    pin = require_final_cert_pilot_waiver()
    assert pin["atlas_2_0_final_cert_pilot_mode"] == WAIVER_MODE
    assert pin["authentic_estate_pilot"] is False
    assert pin["owner_waived"] is True


def test_sync_production(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = build_sync_production_plan(vault, plan_id="plan-a")
    assert report["production"] is True
    assert report["authentic_estate_pilot"] is False
    assert report["honest_label"] == HONEST_LABEL
    validate_record(report, "sync-production-plan")


def test_sync_rejects_non_fixture(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(SyncProductionError, match="evidence-class-must-be-fixture"):
        build_sync_production_plan(
            vault,
            plan_id="plan-a",
            projects=[
                {
                    "project_id": "x",
                    "disposition": "eligible",
                    "evidence_class": "estate",
                }
            ],
        )


def test_twin_production(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = build_twin_production_projection(vault, projection_id="proj-a")
    assert report["twin_production_ready"] is True
    assert report["estate_pilot_passed"] is False
    assert report["authentic_estate_pilot"] is False
    validate_record(report, "twin-production-projection")


def test_docs_and_schemas() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "docs" / "AS-2.0-FINAL-CERT-PILOT-WAIVER.md").is_file()
    assert (root / "docs" / "AS-2.0-SYNC-001.md").is_file()
    assert (root / "docs" / "AS-2.0-TWIN-001.md").is_file()
    assert "sync-production-plan" in available_schemas()
    assert "twin-production-projection" in available_schemas()
