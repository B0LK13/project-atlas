"""AS-2.2-ESTATE-OPS-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "estate-ops"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-ESTATE-OPS-DEEPEN-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-ESTATE-OPS-001-estate-ops-lens-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "estate-ops-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-deepen-unknown-as-healthy.expect.json": "action",
    "negative-deepen-ui-canonical-write.expect.json": "action",
    "negative-deepen-pilot-invent.expect.json": "action",
    "negative-deepen-ops-runtime-mutation.expect.json": "action",
    "negative-deepen-llm-authority.expect.json": "action",
}

EVIDENCE_WALL = {
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
        assert "ESTATE-OPS" in text or "estate-ops" in text.lower() or "ESTATE OPS" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()


def test_deepen_path_extends_base_estate_ops_without_relocation() -> None:
    """Deepen tree must reference but not relocate base stub paths."""
    assert (CONTRACTS / "estate-ops-cockpit-view.schema.json").is_file()
    assert (CONTRACTS / "estate-ops-action.schema.json").is_file()
    assert (FIXTURES / "cockpit-estate-selected.sample.json").is_file()
    assert (FIXTURES / "negative-unknown-as-healthy.expect.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "estate-ops/" in package
    assert "deepen" in package.lower()
    assert "do not dual-own" in package.lower() or "do not relocate" in package.lower()
    assert (PREP / "AS-2.2-ESTATE-OPS-PREP-001.md").is_file()
    # Dedicated forbidden-action stub must not collide with base action stub name.
    assert SCHEMA_FILES["action"] != "estate-ops-action.schema.json"


def test_contract_stub_exists_and_is_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    filename = SCHEMA_FILES["action"]
    stub = CONTRACTS / filename
    assert stub.is_file(), stub
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "estate" in body.lower() or "ops" in body.lower()
    kind = _load_json(stub)
    assert isinstance(kind, dict)
    assert "enum" in kind["properties"]["kind"]
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
    assert "ops_health" in text or "Layer B" in text


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "unknown" in text.lower()
    assert "healthy" in text.lower()
    assert "UI ≠ canonical" in text or "UI≠canonical" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text


def test_negative_actions_are_rejected_forbidden_with_evidence_wall() -> None:
    cases = {
        "negative-deepen-unknown-as-healthy.expect.json": (
            "unknown_as_healthy",
            "estate-ops-unknown-as-healthy-forbidden",
        ),
        "negative-deepen-ui-canonical-write.expect.json": (
            "ui_canonical_write",
            "estate-ops-ui-canonical-write-forbidden",
        ),
        "negative-deepen-pilot-invent.expect.json": (
            "pilot_invent",
            "estate-ops-pilot-invent-forbidden",
        ),
        "negative-deepen-ops-runtime-mutation.expect.json": (
            "ops_runtime_mutation",
            "estate-ops-ops-runtime-mutation-forbidden",
        ),
        "negative-deepen-llm-authority.expect.json": (
            "llm_authority_stamp",
            "estate-ops-llm-authority-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"
        for key, expected in EVIDENCE_WALL.items():
            assert payload[key] == expected, (name, key)


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-deepen-llm-authority.expect.json")
    assert isinstance(bad, dict)
    del bad["truth_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_forbidden_action_schema_rejects_canonical_writes_true() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-deepen-ui-canonical-write.expect.json")
    assert isinstance(bad, dict)
    bad["canonical_writes"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_production_mutation_paths_in_prep_tree() -> None:
    """Prep must not touch shared production mutation surfaces."""
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        text=True,
    )
    changed = {line.strip().replace("\\", "/") for line in diff.splitlines() if line.strip()}
    forbidden = [
        "src/project_atlas/ops_health.py",
        "src/project_atlas/ops_events.py",
        "src/project_atlas/knowledge_compiler.py",
        "docs/atlas-2.2/README.md",
    ]
    for rel in forbidden:
        assert rel not in changed
    for name in changed:
        assert not name.startswith("src/"), name
        assert not name.startswith("apps/"), name
        assert not name.endswith("README.md"), name
        assert name.startswith("docs/atlas-2.2/estate-ops/") or name in {
            "tests/unit/test_as_2_2_estate_ops_deepen_prep_001.py",
            "tests/unit/test_as_2_2_estate_ops_prep_001.py",
        }, name
