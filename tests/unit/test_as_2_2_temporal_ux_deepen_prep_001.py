"""AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "temporal-ux"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "base_package": PREP / "AS-2.2-TEMPORAL-UX-PREP-001.md",
    "adr": PREP / "adr" / "ADR-2.2-TEMPORAL-UX-001-validity-lens-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-deepen-wall-clock.expect.json": "action",
    "negative-deepen-silent-winner.expect.json": "action",
    "negative-deepen-bitemporal-mutation.expect.json": "action",
    "negative-deepen-llm-authority.expect.json": "action",
    "negative-deepen-canonical-write.expect.json": "action",
    "negative-deepen-pilot-invent.expect.json": "action",
    "negative-deepen-release-cert-stamp.expect.json": "action",
}

HONESTY = {
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
        assert "TEMPORAL" in text.upper() or "temporal" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))


def test_deepen_path_extends_base_without_relocation() -> None:
    """Deepen tree must reference but not relocate base stub paths."""
    assert (CONTRACTS / "temporal-action.schema.json").is_file()
    assert (CONTRACTS / "temporal-cockpit-view.schema.json").is_file()
    assert (FIXTURES / "negative-wall-clock.expect.json").is_file()
    assert (FIXTURES / "cockpit-as-of-selected.sample.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "temporal-ux/" in package
    assert "deepen" in package.lower()
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    assert DOCS["base_package"].is_file()


def test_forbidden_action_schema_exists_and_is_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    filename = SCHEMA_FILES["action"]
    stub = CONTRACTS / filename
    assert stub.is_file(), stub
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "enum" in body
    assert "wall_clock_as_of" in body
    assert "silent_winner" in body
    assert "bitemporal_mutation" in body
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
    assert "bitemporal" in text
    assert "do not mutate" in text.lower() or "NONE" in text


def test_negative_actions_are_rejected_forbidden_with_honesty_walls() -> None:
    cases = {
        "negative-deepen-wall-clock.expect.json": (
            "wall_clock_as_of",
            "temporal-ux-wall-clock-forbidden",
        ),
        "negative-deepen-silent-winner.expect.json": (
            "silent_winner",
            "temporal-ux-silent-winner-forbidden",
        ),
        "negative-deepen-bitemporal-mutation.expect.json": (
            "bitemporal_mutation",
            "temporal-ux-bitemporal-mutation-forbidden",
        ),
        "negative-deepen-llm-authority.expect.json": (
            "llm_authority_stamp",
            "temporal-ux-llm-authority-forbidden",
        ),
        "negative-deepen-canonical-write.expect.json": (
            "ui_canonical_write",
            "temporal-ux-ui-canonical-write-forbidden",
        ),
        "negative-deepen-pilot-invent.expect.json": (
            "pilot_invent",
            "temporal-ux-pilot-invent-forbidden",
        ),
        "negative-deepen-release-cert-stamp.expect.json": (
            "release_cert_stamp",
            "temporal-ux-release-cert-stamp-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["package_id"] == "AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001"
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"
        for key, value in HONESTY.items():
            assert payload[key] == value, (name, key)
        assert payload.get("pilot_roots", 0) == 0


def test_forbidden_action_schema_rejects_honesty_wall_violations() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-deepen-pilot-invent.expect.json")
    assert isinstance(bad, dict)
    bad["release_certified"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-deepen-llm-authority.expect.json")
    assert isinstance(bad, dict)
    del bad["truth_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_base_peer_negatives_remain_untouched() -> None:
    base = _load_json(FIXTURES / "negative-wall-clock.expect.json")
    assert isinstance(base, dict)
    assert base["package_id"] == "AS-2.2-TEMPORAL-UX-PREP-001"
    assert base["kind"] == "wall_clock_as_of"


def test_no_production_mutation_paths_in_prep_tree() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'temporal-ux' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("temporal-ux")
