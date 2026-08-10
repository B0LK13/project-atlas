"""AS-2.2-DOC-CHARTER-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "doc-charter"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-DOC-CHARTER-DEEPEN-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "base_package": PREP / "AS-2.2-DOC-CHARTER-PREP-001.md",
    "adr": PREP / "adr" / "ADR-2.2-DOC-CHARTER-001-charter-maturity-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "doc-charter-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-deepen-release-cert-stamp.expect.json": "action",
    "negative-deepen-unlock-stamp.expect.json": "action",
    "negative-deepen-pilot-invent.expect.json": "action",
    "negative-deepen-matrix-cert-promotion.expect.json": "action",
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


def test_prep_docs_exist_without_readme() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "DOC-CHARTER" in text.upper() or "doc-charter" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))


def test_deepen_path_extends_base_without_relocation() -> None:
    """Deepen tree must reference but not relocate base stub paths."""
    assert (CONTRACTS / "charter-maturity-row.schema.json").is_file()
    assert (CONTRACTS / "charter-maturity-matrix.schema.json").is_file()
    assert (FIXTURES / "negative-release-certified.expect.json").is_file()
    assert (FIXTURES / "maturity-matrix.fixture.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "doc-charter/" in package
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
    assert "release_cert_stamp" in body
    assert "unlock_stamp" in body
    assert "matrix_cert_promotion" in body
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
        "negative-deepen-release-cert-stamp.expect.json": (
            "release_cert_stamp",
            "doc-charter-release-cert-stamp-forbidden",
        ),
        "negative-deepen-unlock-stamp.expect.json": (
            "unlock_stamp",
            "doc-charter-unlock-stamp-forbidden",
        ),
        "negative-deepen-pilot-invent.expect.json": (
            "pilot_invent",
            "doc-charter-pilot-invent-forbidden",
        ),
        "negative-deepen-matrix-cert-promotion.expect.json": (
            "matrix_cert_promotion",
            "doc-charter-matrix-cert-promotion-forbidden",
        ),
        "negative-deepen-runtime-mutation.expect.json": (
            "runtime_mutation",
            "doc-charter-runtime-mutation-forbidden",
        ),
        "negative-deepen-llm-authority.expect.json": (
            "llm_authority_stamp",
            "doc-charter-llm-authority-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["package_id"] == "AS-2.2-DOC-CHARTER-DEEPEN-PREP-001"
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
    base = _load_json(FIXTURES / "negative-release-certified.expect.json")
    assert isinstance(base, dict)
    assert base["package_id"] == "AS-2.2-DOC-CHARTER-PREP-001"
    assert base["expected_error"] == "doc-charter-prep-release-certified-forbidden"


def test_no_production_mutation_paths_in_prep_tree() -> None:
    """Prep must not touch shared production mutation surfaces."""
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        text=True,
    )
    changed = {line.strip().replace("\\", "/") for line in diff.splitlines() if line.strip()}
    forbidden = [
        "src/project_atlas/knowledge_compiler.py",
        "docs/atlas-2.2/README.md",
        "docs/atlas-2.2/CHARTER.md",
    ]
    for rel in forbidden:
        assert rel not in changed
    for name in changed:
        assert not name.startswith("src/"), name
        assert not name.startswith("apps/"), name
        assert (
            name.startswith("docs/atlas-2.2/doc-charter/")
            or name == "tests/unit/test_as_2_2_doc_charter_deepen_prep_001.py"
        ), name
        assert not name.endswith("README.md"), name
