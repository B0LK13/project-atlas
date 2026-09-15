"""AS-2.2-INTEL-SLICE-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "intel-slice"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-INTEL-SLICE-DEEPEN-PREP-001.md",
    "base_package": PREP / "AS-2.2-INTEL-SLICE-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "DEEPEN-FIXTURE-PLAN.md",
    "base_fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-INTEL-SLICE-001-deepen-prep.md",
}

BASE_NEGATIVES = (
    "negative-authority-elevation.expect.json",
    "negative-silent-conflict-resolve.expect.json",
    "negative-llm-authority.expect.json",
    "negative-canonical-write.expect.json",
)

SCHEMA_FILES = {
    "action": "intel-slice-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-release-cert-stamp.expect.json": "action",
    "negative-pilot-invent.expect.json": "action",
    "negative-llm-authority-stamp.expect.json": "action",
}

EVIDENCE_FIELDS = {
    "evidence_class": "fixture-only",
    "authentic_estate": False,
    "release_certified": False,
    "pilot_pass": False,
    "canonical_writes": False,
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist_without_readme() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "INTEL" in text.upper() or "intel" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))


def test_deepen_path_extends_base_without_relocation() -> None:
    """Deepen must reference base fixtures and must not relocate them."""
    for filename in BASE_NEGATIVES:
        assert (FIXTURES / filename).is_file(), filename
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "deepen" in package.lower()
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    assert "DEMO VERIFIED" in package
    assert (CONTRACTS / SCHEMA_FILES["action"]).is_file()
    # Deepen llm stamp fixture is additive; base llm-authority remains peer.
    assert (FIXTURES / "negative-llm-authority.expect.json").is_file()
    assert (FIXTURES / "negative-llm-authority-stamp.expect.json").is_file()
    assert SCHEMA_FILES["action"] != "negative-llm-authority.expect.json"


def test_contract_stub_exists_and_is_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    filename = SCHEMA_FILES["action"]
    stub = CONTRACTS / filename
    assert stub.is_file(), stub
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "intel-slice" in body.lower() or "intel slice" in body.lower()
    assert not (package_schemas / filename).exists()


def test_forbidden_action_schema_enum_vocabulary() -> None:
    schema = _schema("action")
    kinds = schema["properties"]["kind"]["enum"]
    for required in (
        "release_cert_stamp",
        "pilot_invent",
        "llm_authority_stamp",
        "authority_elevation",
        "silent_conflict_resolve",
        "canonical_write",
    ):
        assert required in kinds


def test_fixtures_validate_against_prep_stubs() -> None:
    for fixture_name, schema_key in FIXTURE_SCHEMA.items():
        fixture_path = FIXTURES / fixture_name
        assert fixture_path.is_file(), fixture_path
        instance = _load_json(fixture_path)
        schema = _schema(schema_key)
        jsonschema.validate(instance=instance, schema=schema)


def test_package_card_non_claims() -> None:
    text = DOCS["package"].read_text(encoding="utf-8")
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "**NO**" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "Layer B" in text or "canonical" in text.lower()
    assert "2fe504914eadef7d453b773fa4d96e3bb4175f47" in text
    assert "3d82fa7552280afd82d68f8313dde5bfdaa30d9d" in text


def test_invariants_document_deepen_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "release_cert_stamp" in text or "RELEASE CERT" in text
    assert "pilot_invent" in text or "PILOT" in text.upper()
    assert "llm_authority" in text.lower() or "LLM" in text.upper()
    assert "DEMO VERIFIED" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text
    assert "do not relocate" in text.lower()


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-release-cert-stamp.expect.json": (
            "release_cert_stamp",
            "intel-slice-release-cert-stamp-forbidden",
        ),
        "negative-pilot-invent.expect.json": (
            "pilot_invent",
            "intel-slice-pilot-invent-forbidden",
        ),
        "negative-llm-authority-stamp.expect.json": (
            "llm_authority_stamp",
            "intel-slice-llm-authority-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"
        assert payload["package_id"] == "AS-2.2-INTEL-SLICE-DEEPEN-PREP-001"
        for field, expected in EVIDENCE_FIELDS.items():
            assert payload[field] == expected, (name, field)


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-llm-authority-stamp.expect.json")
    assert isinstance(bad, dict)
    del bad["truth_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_forbidden_action_schema_rejects_release_certified_true() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-release-cert-stamp.expect.json")
    assert isinstance(bad, dict)
    bad["release_certified"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_base_negatives_remain_untouched() -> None:
    """Deepen must not relocate base informal negatives."""
    for name in BASE_NEGATIVES:
        path = FIXTURES / name
        assert path.is_file(), name
        payload = _load_json(path)
        assert isinstance(payload, dict)
        assert payload["package_id"] == "AS-2.2-INTEL-SLICE-PREP-001"
        assert payload["status"] == "rejected_forbidden"


def test_no_production_semantic_mutation_paths_in_prep_tree() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'intel-slice' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("intel-slice")
