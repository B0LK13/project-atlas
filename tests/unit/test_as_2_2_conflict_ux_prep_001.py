"""AS-2.2-CONFLICT-UX-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

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
    "package": PREP / "AS-2.2-CONFLICT-UX-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-CONFLICT-UX-001-review-cockpit.md",
}

SCHEMA_FILES = {
    "cockpit": "conflict-cockpit-view.schema.json",
    "card": "conflict-projection-card.schema.json",
    "queue": "review-queue-slice.schema.json",
    "action": "disposition-action.schema.json",
}

FIXTURE_SCHEMA = {
    "cockpit-open-conflict.sample.json": "cockpit",
    "projection-card-duplicate-source.sample.json": "card",
    "review-queue-slice.sample.json": "queue",
    "negative-auto-resolve.expect.json": "action",
    "negative-ui-write.expect.json": "action",
    "negative-authority-elevation.expect.json": "action",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist_without_readme() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "AS-2.2-CONFLICT-UX" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))


def test_contract_stubs_exist_and_are_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    for filename in SCHEMA_FILES.values():
        stub = CONTRACTS / filename
        assert stub.is_file(), stub
        body = stub.read_text(encoding="utf-8")
        assert "PREP STUB" in body
        assert "conflict" in body.lower()
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
    assert "conflict_projections" in text
    assert "do not mutate" in text.lower() or "NONE" in text


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "auto-resolve" in text.lower() or "auto_resolve" in text
    assert "UI ≠ canonical" in text or "UI≠canonical" in text
    assert "LLM ≠ authority" in text or "LLM≠authority" in text
    assert "conflict_projections" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text


def test_open_cockpit_exposes_duplicate_source_and_derived_authority() -> None:
    cockpit = _load_json(FIXTURES / "cockpit-open-conflict.sample.json")
    assert isinstance(cockpit, dict)
    assert cockpit["package_id"] == "AS-2.2-CONFLICT-UX-PREP-001"
    assert cockpit["authority"]["level"] == "derived"
    assert cockpit["evidence_class"] == "fixture-only"
    assert cockpit["pilot_roots"] == 0
    card = cockpit["cards"][0]
    assert card["state"] == "open"
    assert card["duplicate_source"]["kind"] == "duplicate-source"
    assert len(card["duplicate_source"]["source_ids"]) >= 2
    assert card["authority"]["level"] == "derived"


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-auto-resolve.expect.json": (
            "auto_resolve",
            "conflict-ux-auto-resolve-forbidden",
        ),
        "negative-ui-write.expect.json": (
            "ui_canonical_write",
            "conflict-ux-ui-canonical-write-forbidden",
        ),
        "negative-authority-elevation.expect.json": (
            "authority_elevation",
            "conflict-ux-authority-elevation-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"


def test_card_schema_rejects_single_side() -> None:
    schema = _schema("card")
    bad = _load_json(FIXTURES / "projection-card-duplicate-source.sample.json")
    assert isinstance(bad, dict)
    bad["sides"] = bad["sides"][:1]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_runtime_conflict_projections_mutation() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'conflict-ux' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("conflict-ux")
