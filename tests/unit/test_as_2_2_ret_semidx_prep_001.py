"""AS-2.2-RET-SEMIDX-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "ret-semidx"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-RET-SEMIDX-PREP-001.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-RET-SEMIDX-001-semantic-index-prep.md",
}

FIXTURES_MAP = {
    "negative-semantic-as-authority.expect.json": "semantic_as_authority",
    "negative-default-enable-semantic.expect.json": "default_enable_semantic",
    "negative-release-cert-stamp.expect.json": "release_cert_stamp",
    "negative-unlock-stamp.expect.json": "unlock_stamp",
    "negative-pilot-invent.expect.json": "pilot_invent",
    "negative-layer-b-write.expect.json": "layer_b_write",
    "negative-llm-authority.expect.json": "llm_authority_stamp",
}


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_semidx_docs_exist() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "SEMIDX" in text.upper() or "semantic" in text.lower()
        assert "PREP" in text.upper() or "prep" in text


def test_forbidden_schema_not_package_data() -> None:
    stub = CONTRACTS / "ret-semidx-forbidden-action.schema.json"
    assert stub.is_file()
    body = stub.read_text(encoding="utf-8")
    assert "PREP STUB" in body
    assert "semantic_as_authority" in body
    assert "default_enable_semantic" in body
    assert not (ROOT / "src" / "project_atlas" / "schemas" / stub.name).exists()


def test_negatives_validate_and_honesty_walls() -> None:
    schema = _load(CONTRACTS / "ret-semidx-forbidden-action.schema.json")
    for name, kind in FIXTURES_MAP.items():
        inst = _load(FIXTURES / name)
        assert isinstance(inst, dict)
        jsonschema.validate(instance=inst, schema=schema)
        assert inst["kind"] == kind
        assert inst["status"] == "rejected_forbidden"
        assert inst["evidence_class"] == "fixture-only"
        assert inst["authentic_estate"] is False
        assert inst["release_certified"] is False
        assert inst["pilot_pass"] is False
        assert inst["canonical_writes"] is False
        assert inst["semantic_enabled_default"] is False
        assert inst["pilot_roots"] == 0


def test_package_non_claims() -> None:
    text = DOCS["package"].read_text(encoding="utf-8")
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "**NO**" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "Production mutation" in text and "NONE" in text
    assert "do not dual-own" in text.lower()
