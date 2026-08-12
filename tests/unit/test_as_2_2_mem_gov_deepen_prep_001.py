"""AS-2.2-MEM-GOV-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "mem-gov"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"
BASE_CONTRACTS = ROOT / "docs" / "atlas-2.2" / "contracts" / "mem-gov"
BASE_FIXTURES = ROOT / "docs" / "atlas-2.2" / "fixtures" / "mem-gov"

DOCS = {
    "package": PREP / "AS-2.2-MEM-GOV-DEEPEN-PREP-001.md",
    "readme": PREP / "README.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-MEM-GOV-001-governed-agent-memory-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "mem-gov-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-layer-b-promotion.expect.json": "action",
    "negative-llm-authority.expect.json": "action",
    "negative-dual-active.expect.json": "action",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "AS-2.2-MEM-GOV" in text or "mem-gov" in text.lower()
        assert "PREP" in text.upper() or "prep" in text


def test_deepen_path_extends_base_mem_gov_without_relocation() -> None:
    """Deepen tree must reference but not relocate base stub paths."""
    assert BASE_CONTRACTS.is_dir()
    assert BASE_FIXTURES.is_dir()
    assert (BASE_CONTRACTS / "agent-memory-record.schema.json").is_file()
    assert (BASE_FIXTURES / "active-memory.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "contracts/mem-gov/" in package
    assert "fixtures/mem-gov/" in package
    assert "deepen" in package.lower()
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    # Deepen forbidden-action stub must not collide with base record schema name.
    assert not (BASE_CONTRACTS / SCHEMA_FILES["action"]).exists()


def test_contract_stub_exists_and_is_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    filename = SCHEMA_FILES["action"]
    stub = CONTRACTS / filename
    assert stub.is_file(), stub
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "mem-gov" in body.lower() or "agent memory" in body.lower()
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
    assert "knowledge_compiler" in text or "Layer B" in text


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "MEMORY ≠ LAYER B" in text or "Memory ≠ Layer B" in text
    assert "PROVENANCE" in text.upper() or "provenance" in text
    assert "dual-active" in text.lower() or "DUAL-ACTIVE" in text
    assert "INT-011" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-layer-b-promotion.expect.json": (
            "layer_b_promotion",
            "mem-gov-layer-b-promotion-forbidden",
        ),
        "negative-llm-authority.expect.json": (
            "llm_authority_stamp",
            "mem-gov-llm-authority-forbidden",
        ),
        "negative-dual-active.expect.json": (
            "dual_active_fork",
            "mem-gov-dual-active-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority_plane"] == "none"
        assert payload["consume_only"] is True


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-llm-authority.expect.json")
    assert isinstance(bad, dict)
    del bad["truth_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_production_semantic_mutation_paths_in_prep_tree() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'mem-gov' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("mem-gov")
