"""AS-2.2-MEM-GOV-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2"
CONTRACTS = PREP / "contracts" / "mem-gov"
FIXTURES = PREP / "fixtures" / "mem-gov"
DOCS = {
    "package": ROOT / "docs" / "AS-2.2-MEM-GOV-001.md",
    "readme": PREP / "mem-gov" / "README.md",
    "architecture": PREP / "mem-gov" / "ARCHITECTURE.md",
    "contract": PREP / "mem-gov" / "CONTRACT.md",
    "adr": PREP / "adr" / "ADR-2.2-MEM-GOV-001-governed-agent-memory.md",
}

SCHEMA_FILES = {
    "record": "agent-memory-record.schema.json",
    "provenance": "agent-memory-provenance.schema.json",
    "revocation": "agent-memory-revocation.schema.json",
    "expiry": "agent-memory-expiry.schema.json",
    "supersession": "agent-memory-supersession.schema.json",
    "index": "agent-memory-index.schema.json",
}

FIXTURE_SCHEMA = {
    "active-memory.json": "record",
    "revoked-memory.json": "record",
    "superseded-prior.json": "record",
    "superseding-successor.json": "record",
    "revocation-event.json": "revocation",
    "expiry-as-of-past.json": "expiry",
    "expiry-as-of-before.json": "expiry",
    "supersession-edge.json": "supersession",
    "memory-index.json": "index",
    "provenance-only.json": "provenance",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "AS-2.2-MEM-GOV" in text
        assert "PREP" in text.upper() or "prep" in text


def test_contract_stubs_exist_and_are_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    for filename in SCHEMA_FILES.values():
        stub = CONTRACTS / filename
        assert stub.is_file(), stub
        body = stub.read_text(encoding="utf-8")
        assert "PREP STUB" in body
        assert "atlas.2.2.agent_memory" in body or "agent-memory" in body
        # Must not land as installed package data in this PREP.
        assert not (package_schemas / filename).exists()


def test_fixtures_validate_against_prep_stubs() -> None:
    for fixture_name, schema_key in FIXTURE_SCHEMA.items():
        fixture_path = FIXTURES / fixture_name
        assert fixture_path.is_file(), fixture_path
        instance = _load_json(fixture_path)
        schema = _schema(schema_key)
        jsonschema.validate(instance=instance, schema=schema)


def test_active_memory_requires_provenance_and_non_authority() -> None:
    record = _load_json(FIXTURES / "active-memory.json")
    assert isinstance(record, dict)
    assert record["authority_plane"] == "none"
    assert record["consume_only"] is True
    assert record["status"] == "active"
    prov = record["provenance"]
    assert isinstance(prov, dict)
    assert len(prov["content_sha256"]) == 64
    assert prov["source_receipt_id"]
    assert prov["session_id"]


def test_revoked_memory_not_active() -> None:
    record = _load_json(FIXTURES / "revoked-memory.json")
    assert isinstance(record, dict)
    assert record["status"] == "revoked"
    assert record["revocation"]["reason"] == "operator"
    assert record["status"] != "active"


def test_expiry_as_of_semantics() -> None:
    past = _load_json(FIXTURES / "expiry-as-of-past.json")
    before = _load_json(FIXTURES / "expiry-as-of-before.json")
    assert isinstance(past, dict) and isinstance(before, dict)
    assert past["effective_status"] == "expired"
    assert before["effective_status"] == "active"
    assert past["as_of"] > past["expires_at"]
    assert before["as_of"] < before["expires_at"]


def test_supersession_is_reciprocal() -> None:
    prior = _load_json(FIXTURES / "superseded-prior.json")
    successor = _load_json(FIXTURES / "superseding-successor.json")
    edge = _load_json(FIXTURES / "supersession-edge.json")
    assert isinstance(prior, dict) and isinstance(successor, dict)
    assert isinstance(edge, dict)
    assert prior["memory_key"] == successor["memory_key"]
    assert prior["status"] == "superseded"
    assert prior["superseded_by"] == successor["memory_id"]
    assert successor["supersedes"] == prior["memory_id"]
    assert successor["status"] == "active"
    assert edge["reciprocal"] is True
    assert edge["prior_memory_id"] == prior["memory_id"]
    assert edge["successor_memory_id"] == successor["memory_id"]


def test_index_lists_non_authority_plane() -> None:
    index = _load_json(FIXTURES / "memory-index.json")
    assert isinstance(index, dict)
    assert index["authority_plane"] == "none"
    assert index["truth_plane"] == "operational"
    statuses = {row["status"] for row in index["records"]}
    assert statuses == {"active", "revoked", "superseded"}


def test_record_schema_rejects_missing_provenance() -> None:
    schema = _schema("record")
    bad = _load_json(FIXTURES / "active-memory.json")
    assert isinstance(bad, dict)
    del bad["provenance"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_production_semantic_mutation_paths_in_prep_tree() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'mem-gov' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("mem-gov")
