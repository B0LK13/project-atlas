"""AS-2.2-DOD-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "dod-compiler"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"
BASE_CONTRACTS = ROOT / "docs" / "atlas-2.2" / "contracts" / "dod-compiler"
BASE_FIXTURES = ROOT / "docs" / "atlas-2.2" / "fixtures" / "dod-compiler"

DOCS = {
    "package": PREP / "AS-2.2-DOD-DEEPEN-PREP-001.md",
    "readme": PREP / "README.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-DOD-002-dod-compiler-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "dod-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-layer-b-promotion.expect.json": "action",
    "negative-llm-authority.expect.json": "action",
    "negative-pilot-invent.expect.json": "action",
    "negative-invented-pass.expect.json": "action",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "AS-2.2-DOD" in text or "DoD" in text or "dod-compiler" in text.lower()
        assert "PREP" in text.upper() or "prep" in text


def test_deepen_path_extends_base_dod_without_relocation() -> None:
    """Deepen tree must reference but not relocate base stub paths."""
    assert BASE_CONTRACTS.is_dir()
    assert BASE_FIXTURES.is_dir()
    assert (BASE_CONTRACTS / "dod-proof-receipt.schema.json").is_file()
    assert (BASE_FIXTURES / "expected-proof-pass.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "contracts/dod-compiler/" in package
    assert "fixtures/dod-compiler/" in package
    assert "deepen" in package.lower()
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    assert not (BASE_CONTRACTS / SCHEMA_FILES["action"]).exists()


def test_contract_stub_exists_and_is_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    filename = SCHEMA_FILES["action"]
    stub = CONTRACTS / filename
    assert stub.is_file(), stub
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "dod" in body.lower() or "definition-of-done" in body.lower()
    assert not (package_schemas / filename).exists()


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
    assert "Layer B" in text or "knowledge_compiler" in text


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "PROOF ≠ LAYER B" in text or "Proof ≠ Layer B" in text
    assert "EVIDENCE CLASS" in text.upper() or "evidence class" in text
    assert "INVENTED PASS" in text.upper() or "invented pass" in text
    assert "LLM ≠ authority" in text or "LLM ≠ AUTHORITY" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-layer-b-promotion.expect.json": (
            "layer_b_promotion",
            "dod-layer-b-promotion-forbidden",
        ),
        "negative-llm-authority.expect.json": (
            "llm_authority_stamp",
            "dod-llm-authority-forbidden",
        ),
        "negative-pilot-invent.expect.json": (
            "fixture_as_authentic_pilot",
            "dod-fixture-as-pilot-forbidden",
        ),
        "negative-invented-pass.expect.json": (
            "invented_pass",
            "dod-invented-pass-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority_promoted"] is False
        assert payload["consume_only"] is True
        assert payload["pilot_roots"] == 0


def test_fx_dod_004_unknown_criterion_fixture_exists() -> None:
    proof = _load_json(BASE_FIXTURES / "expected-proof-fail-unknown-criterion.json")
    assert isinstance(proof, dict)
    assert proof["status"] == "FAIL"
    orphan = next(
        row
        for row in proof["criterion_results"]
        if row["criterion_id"] == "crit.demo.orphan-binding"
    )
    assert orphan["reason_codes"] == ["unknown_criterion"]


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-llm-authority.expect.json")
    assert isinstance(bad, dict)
    del bad["truth_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_production_mutation_paths_in_prep_tree() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'dod-compiler' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("dod-compiler")
