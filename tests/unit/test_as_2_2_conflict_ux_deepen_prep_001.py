"""AS-2.2-CONFLICT-UX-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "conflict-ux"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-CONFLICT-UX-DEEPEN-PREP-001.md",
    "base_package": PREP / "AS-2.2-CONFLICT-UX-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "DEEPEN-FIXTURE-PLAN.md",
    "base_fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-CONFLICT-UX-002-deepen-prep.md",
}

BASE_SCHEMAS = {
    "cockpit": "conflict-cockpit-view.schema.json",
    "card": "conflict-projection-card.schema.json",
    "queue": "review-queue-slice.schema.json",
    "disposition": "disposition-action.schema.json",
}

SCHEMA_FILES = {
    "action": "conflict-ux-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-release-cert-stamp.expect.json": "action",
    "negative-pilot-invent.expect.json": "action",
    "negative-llm-authority.expect.json": "action",
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
        assert "CONFLICT" in text.upper() or "conflict" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))


def test_deepen_path_extends_base_without_relocation() -> None:
    """Deepen must reference base stubs and must not relocate them."""
    for filename in BASE_SCHEMAS.values():
        assert (CONTRACTS / filename).is_file(), filename
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "disposition-action" in package or "disposition" in package.lower()
    assert "deepen" in package.lower()
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    assert "DEMO VERIFIED" in package
    # Forbidden-action is deepen-only; base disposition schema stays put.
    assert (CONTRACTS / BASE_SCHEMAS["disposition"]).is_file()
    assert (CONTRACTS / SCHEMA_FILES["action"]).is_file()
    assert SCHEMA_FILES["action"] != BASE_SCHEMAS["disposition"]


def test_contract_stub_exists_and_is_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    filename = SCHEMA_FILES["action"]
    stub = CONTRACTS / filename
    assert stub.is_file(), stub
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "conflict-ux" in body.lower() or "conflict ux" in body.lower()
    assert not (package_schemas / filename).exists()


def test_forbidden_action_schema_enum_vocabulary() -> None:
    schema = _schema("action")
    kinds = schema["properties"]["kind"]["enum"]
    for required in (
        "release_cert_stamp",
        "pilot_invent",
        "llm_authority_stamp",
        "auto_resolve",
        "ui_canonical_write",
        "authority_elevation",
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
    assert "conflict_projections" in text or "Layer B" in text
    assert "b431494dc8860f4f1db3f327c9ccf991699ccfc5" in text
    assert "26a59cd76bd9df410912b4552ddd907f7a160588" in text


def test_invariants_document_deepen_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "release_cert_stamp" in text or "RELEASE CERT" in text
    assert "pilot_invent" in text or "PILOT" in text.upper()
    assert "llm_authority" in text.lower() or "LLM" in text.upper()
    assert "DEMO VERIFIED" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text
    assert "do not relocate" in text.lower() or "disposition-action" in text


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-release-cert-stamp.expect.json": (
            "release_cert_stamp",
            "conflict-ux-release-cert-stamp-forbidden",
        ),
        "negative-pilot-invent.expect.json": (
            "pilot_invent",
            "conflict-ux-pilot-invent-forbidden",
        ),
        "negative-llm-authority.expect.json": (
            "llm_authority_stamp",
            "conflict-ux-llm-authority-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"
        for field, expected in EVIDENCE_FIELDS.items():
            assert payload[field] == expected, (name, field)


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-llm-authority.expect.json")
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


def test_base_disposition_negatives_remain_untouched() -> None:
    """Deepen must not relocate base disposition fixtures / schema."""
    for name in (
        "negative-auto-resolve.expect.json",
        "negative-ui-write.expect.json",
        "negative-authority-elevation.expect.json",
    ):
        path = FIXTURES / name
        assert path.is_file(), name
        payload = _load_json(path)
        assert isinstance(payload, dict)
        assert payload["package_id"] == "AS-2.2-CONFLICT-UX-PREP-001"
    disposition = _load_json(CONTRACTS / BASE_SCHEMAS["disposition"])
    assert isinstance(disposition, dict)
    assert "disposition-action" in disposition.get("title", "").lower() or (
        "disposition" in disposition.get("description", "").lower()
    )


def test_no_production_semantic_mutation_paths_in_prep_tree() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'conflict-ux' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("conflict-ux")
