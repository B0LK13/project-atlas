"""AS-2.2-KF2-FABRIC-DEEPEN-PREP-001 — docs/contracts/fixtures only."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "kf2-fabric"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"
BASE = PREP / "AS-2.2-KF2-FABRIC-PREP-001.md"

FIXTURES_BY_KIND = {
    "authority_elevate": "negative-deepen-authority-elevate.expect.json",
    "cross_promote": "negative-deepen-cross-promote.expect.json",
    "projection_write": "negative-deepen-projection-write.expect.json",
    "layer_b_write": "negative-deepen-layer-b-write.expect.json",
    "release_cert_stamp": "negative-deepen-release-cert-stamp.expect.json",
    "pilot_invent": "negative-deepen-pilot-invent.expect.json",
    "llm_authority_stamp": "negative-deepen-llm-authority.expect.json",
    "kf2_runtime_mutation": "negative-deepen-kf2-runtime-mutation.expect.json",
}


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_kf2_fabric_deepen_docs_present() -> None:
    for name in (
        "AS-2.2-KF2-FABRIC-DEEPEN-PREP-001.md",
        "INVARIANTS.md",
        "DEEPEN-FIXTURE-PLAN.md",
        "adr/ADR-2.2-KF2-FABRIC-002-deepen-prep.md",
    ):
        path = PREP / name
        assert path.is_file(), name
        assert "PREP" in path.read_text(encoding="utf-8").upper()
    package = (PREP / "AS-2.2-KF2-FABRIC-DEEPEN-PREP-001.md").read_text(encoding="utf-8")
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in package
    assert "**NO**" in package
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in package


def test_kf2_fabric_deepen_extends_base() -> None:
    assert BASE.is_file()
    package = (PREP / "AS-2.2-KF2-FABRIC-DEEPEN-PREP-001.md").read_text(encoding="utf-8")
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    assert (CONTRACTS / "kf2-estate-fabric-inventory.schema.json").is_file()
    assert (CONTRACTS / "kf2-estate-projection.schema.json").is_file()
    assert (FIXTURES / "negative-cross-promote.expect.json").is_file()
    assert (FIXTURES / "negative-authority-elevate.expect.json").is_file()
    assert (FIXTURES / "negative-projection-write.expect.json").is_file()


def test_kf2_fabric_forbidden_negatives() -> None:
    schema_path = CONTRACTS / "kf2-fabric-forbidden-action.schema.json"
    schema = _load(schema_path)
    assert "PREP STUB" in schema_path.read_text(encoding="utf-8")
    assert schema["properties"]["status"]["const"] == "rejected_forbidden"  # type: ignore[index]
    for kind, filename in FIXTURES_BY_KIND.items():
        payload = _load(FIXTURES / filename)
        jsonschema.validate(payload, schema)  # type: ignore[arg-type]
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["pilot_pass"] is False
        assert payload["release_certified"] is False
        assert payload["canonical_writes"] is False
        assert payload["authentic_estate"] is False
        assert payload["evidence_class"] == "fixture-only"
        assert payload["package_id"] == "AS-2.2-KF2-FABRIC-DEEPEN-PREP-001"


def test_kf2_fabric_forbidden_schema_not_package_data() -> None:
    filename = "kf2-fabric-forbidden-action.schema.json"
    assert (CONTRACTS / filename).is_file()
    assert not (ROOT / "src" / "project_atlas" / "schemas" / filename).exists()
