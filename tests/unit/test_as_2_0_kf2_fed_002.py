"""AS-KF2-002 / AS-2.0-FED-002 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.federation_lens import (
    FederationLensError,
    build_federation_read_lens,
)
from project_atlas.kf2_inventory import build_kf2_fabric_inventory
from project_atlas.schema import available_schemas, validate_record


def test_kf2_inventory(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = build_kf2_fabric_inventory(
        vault, record_id="inv-a", namespace_count=1, entity_count=2, relationship_count=1
    )
    assert report["cross_promote"] is False
    validate_record(report, "kf2-fabric-inventory")


def test_fed_lens(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = build_federation_read_lens(
        vault,
        record_id="lens-a",
        federation_id="fed-a",
        members_visible=["m1", "m2"],
    )
    assert report["cross_vault_promote"] is False
    validate_record(report, "federation-read-lens")


def test_fed_rejects_promote(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(FederationLensError, match="cross-promote-forbidden"):
        build_federation_read_lens(
            vault,
            record_id="lens-a",
            federation_id="fed-a",
            members_visible=["m1"],
            allow_cross_promote=True,
        )


def test_docs_schemas() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "docs" / "AS-KF2-002.md").is_file()
    assert (root / "docs" / "AS-2.0-FED-002.md").is_file()
    assert "kf2-fabric-inventory" in available_schemas()
    assert "federation-read-lens" in available_schemas()
