"""AS-2.2-REALITY-GAP-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "reality-gap"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-REALITY-GAP-DEEPEN-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "deepen_plan": PREP / "DEEPEN-FIXTURE-PLAN.md",
    "base_package": PREP / "AS-2.2-REALITY-GAP-PREP-001.md",
    "adr": PREP / "adr" / "ADR-2.2-REALITY-GAP-001-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "reality-gap-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-deepen-unknown-as-healthy.expect.json": "action",
    "negative-deepen-ui-canonical-write.expect.json": "action",
    "negative-deepen-release-cert-stamp.expect.json": "action",
    "negative-deepen-unlock-stamp.expect.json": "action",
    "negative-deepen-pilot-invent.expect.json": "action",
    "negative-deepen-runtime-mutation.expect.json": "action",
    "negative-deepen-llm-authority.expect.json": "action",
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


def test_prep_docs_exist() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "REALITY" in text.upper() or "reality-gap" in text
        assert "PREP" in text.upper() or "prep" in text


def test_deepen_path_extends_base_without_relocation() -> None:
    assert (CONTRACTS / "reality-gap-prep-inventory.schema.json").is_file()
    assert (CONTRACTS / "reality-gap-prep-scenario.schema.json").is_file()
    assert (FIXTURES / "inventory.fixture.json").is_file()
    assert (FIXTURES / "negative-pilot-invent.fixture.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "reality-gap/" in package
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
    assert "unknown_as_healthy" in body
    assert "ui_canonical_write" in body
    assert "release_cert_stamp" in body
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
    assert "Production mutation" in text and "NONE" in text
    assert "docs/atlas-2.2/README.md" in text


def test_negative_actions_are_rejected_forbidden_with_honesty_walls() -> None:
    cases = {
        "negative-deepen-unknown-as-healthy.expect.json": (
            "unknown_as_healthy",
            "reality-gap-unknown-as-healthy-forbidden",
        ),
        "negative-deepen-ui-canonical-write.expect.json": (
            "ui_canonical_write",
            "reality-gap-ui-canonical-write-forbidden",
        ),
        "negative-deepen-release-cert-stamp.expect.json": (
            "release_cert_stamp",
            "reality-gap-release-cert-stamp-forbidden",
        ),
        "negative-deepen-unlock-stamp.expect.json": (
            "unlock_stamp",
            "reality-gap-unlock-stamp-forbidden",
        ),
        "negative-deepen-pilot-invent.expect.json": (
            "pilot_invent",
            "reality-gap-pilot-invent-forbidden",
        ),
        "negative-deepen-runtime-mutation.expect.json": (
            "runtime_mutation",
            "reality-gap-runtime-mutation-forbidden",
        ),
        "negative-deepen-llm-authority.expect.json": (
            "llm_authority_stamp",
            "reality-gap-llm-authority-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        instance = _load_json(FIXTURES / name)
        assert isinstance(instance, dict)
        assert instance["kind"] == kind
        assert instance["status"] == "rejected_forbidden"
        assert instance["expected_error"] == error
        for key, value in HONESTY.items():
            assert instance[key] == value
        assert instance["pilot_roots"] == 0
