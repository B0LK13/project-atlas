"""AS-2.2-REALITY-LIVE-DEEPEN-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "reality-live"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"
BASE_CONTRACTS = ROOT / "docs" / "atlas-2.2" / "contracts" / "reality-live"

DOCS = {
    "package": PREP / "AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md",
    "readme": PREP / "README.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-REALITY-LIVE-001-live-collectors-deepen-prep.md",
}

SCHEMA_FILES = {
    "action": "reality-live-forbidden-action.schema.json",
}

FIXTURE_SCHEMA = {
    "negative-pilot-invent.expect.json": "action",
    "negative-llm-authority.expect.json": "action",
    "negative-release-cert-stamp.expect.json": "action",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "REALITY-LIVE" in text or "reality-live" in text.lower()
        assert "PREP" in text.upper() or "prep" in text


def test_deepen_path_extends_base_reality_live_without_relocation() -> None:
    """Deepen tree must reference but not relocate base stub paths."""
    assert BASE_CONTRACTS.is_dir()
    assert (BASE_CONTRACTS / "reality-live-planes.schema.draft.json").is_file()
    assert (BASE_CONTRACTS / "reality-live-gap-report.schema.draft.json").is_file()
    assert (FIXTURES / "planes.fixture.json").is_file()
    assert (FIXTURES / "collectors.fixture.json").is_file()
    package = DOCS["package"].read_text(encoding="utf-8")
    assert "contracts/reality-live/" in package
    assert "reality-live/" in package
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
    assert "reality-live" in body.lower()
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
    assert "reality_gap" in text or "Layer B" in text


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "Collectors ≠ Layer B" in text or "COLLECTORS ≠ LAYER B" in text
    assert "UNKNOWN ≠ HEALTHY" in text or "Unknown ≠ healthy" in text
    assert "PILOT" in text.upper()
    assert "REALITY-GAP-001" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-pilot-invent.expect.json": (
            "pilot_invent",
            "reality-live-pilot-invent-forbidden",
        ),
        "negative-llm-authority.expect.json": (
            "llm_authority_stamp",
            "reality-live-llm-authority-forbidden",
        ),
        "negative-release-cert-stamp.expect.json": (
            "release_cert_stamp",
            "reality-live-release-cert-stamp-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"
        assert payload["pilot_roots"] == 0
        assert payload["invent_pilot_roots"] is False


def test_forbidden_action_schema_rejects_missing_required_fields() -> None:
    schema = _schema("action")
    bad = _load_json(FIXTURES / "negative-llm-authority.expect.json")
    assert isinstance(bad, dict)
    del bad["truth_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_production_semantic_mutation_paths_in_prep_tree() -> None:
    """Prep must not touch shared production mutation surfaces."""
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        text=True,
    )
    changed = {line.strip().replace("\\", "/") for line in diff.splitlines() if line.strip()}
    forbidden = [
        "src/project_atlas/reality_gap.py",
        "src/project_atlas/reality_gap_ui.py",
        "src/project_atlas/knowledge_compiler.py",
    ]
    for rel in forbidden:
        assert rel not in changed
    for name in changed:
        assert not name.startswith("src/"), name
        assert name.startswith("docs/atlas-2.2/reality-live/") or name == (
            "tests/unit/test_as_2_2_reality_live_deepen_prep_001.py"
        ), name
