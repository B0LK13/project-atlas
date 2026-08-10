"""AS-2.2-CTX-DEEPEN-PREP-001 - docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "ctx-compiler"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"
BASE_CONTRACTS = ROOT / "docs" / "atlas-2.2" / "contracts" / "ctx-compiler"
BASE_FIXTURES = ROOT / "docs" / "atlas-2.2" / "fixtures" / "ctx-compiler"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ctx_deepen_docs_present() -> None:
    for name in (
        "AS-2.2-CTX-DEEPEN-PREP-001.md",
        "INVARIANTS.md",
        "FIXTURE-PLAN.md",
        "CONTRACT.md",
        "adr/ADR-2.2-CTX-002-context-compiler-deepen-prep.md",
    ):
        path = PREP / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "PREP" in text.upper()
        assert "ATLAS_2_1_RELEASE_CERTIFIED" in text or "RELEASE" in text.upper()


def test_ctx_deepen_extends_base_without_relocation() -> None:
    assert BASE_CONTRACTS.is_dir()
    assert BASE_FIXTURES.is_dir()
    package = (PREP / "AS-2.2-CTX-DEEPEN-PREP-001.md").read_text(encoding="utf-8")
    assert "contracts/ctx-compiler/" in package
    assert "do not dual-own" in package.lower() or "without dual-owning" in package.lower()


def test_ctx_forbidden_action_schema_and_negatives() -> None:
    schema = _load(CONTRACTS / "ctx-forbidden-action.schema.json")
    assert "PREP STUB" in json.dumps(schema)
    for name in (
        "negative-layer-b-write.expect.json",
        "negative-llm-authority.expect.json",
        "negative-budget-invent.expect.json",
    ):
        payload = _load(FIXTURES / name)
        jsonschema.validate(payload, schema)  # type: ignore[arg-type]
        assert payload["expect"] == "reject"
        assert payload["release_certified"] is False
        assert payload["pilot_pass"] is False


def test_ctx_deepen_not_package_data() -> None:
    assert not (
        ROOT / "src" / "project_atlas" / "schemas" / "ctx-forbidden-action.schema.json"
    ).exists()
