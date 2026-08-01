"""Unit tests for JSON schema validation (B-007)."""

from __future__ import annotations

import pytest

from project_atlas.domain import (
    Claim,
    ConceptRecord,
    ConflictRecord,
    ProvenanceReference,
    SourceRecord,
    ValidationFinding,
)
from project_atlas.schema import (
    SchemaValidationError,
    available_schemas,
    load_schema,
    validate_record,
)


def test_all_expected_schemas_available() -> None:
    assert available_schemas() == [
        "claim",
        "concept-record",
        "conflict-record",
        "provenance-reference",
        "semantic-records",
        "source-record",
        "validation-finding",
    ]


def test_schemas_load_and_are_valid() -> None:
    for kind in available_schemas():
        schema = load_schema(kind)
        assert schema["$schema"].startswith("https://json-schema.org/")


def test_unknown_schema_kind_rejected() -> None:
    with pytest.raises(KeyError):
        load_schema("nope")


def test_valid_records_pass() -> None:
    prov = ProvenanceReference(source_id="src-1", resource="sources/x.md")
    source = SourceRecord(source_id="src-1", path="a.md", media_type="text/markdown", size_bytes=1)
    validate_record(source, "source-record")
    concept = ConceptRecord(concept_id="c-1", type="Project", title="t", sources=[prov])
    validate_record(concept, "concept-record")
    claim = Claim(
        claim_id="clm-1", subject="c-1", field="status", value="active", provenance=[prov]
    )
    validate_record(claim, "claim")
    validate_record(prov, "provenance-reference")
    validate_record(
        ConflictRecord(
            conflict_id="conf-1", subject="c-1", field="v",
            claims=[{"source_id": "s-1", "claim": "a"}, {"source_id": "s-2", "claim": "b"}],
        ),
        "conflict-record",
    )
    finding = ValidationFinding(
        finding_id="f-1", rule_id="r", severity="info", gate="content", message="m"
    )
    validate_record(finding, "validation-finding")
    validate_record(
        {"schema_version": 1, "project_id": "p-1", "name": "Project", "generated": True,
         "sources": [], "coverage": []},
        "semantic-records",
    )


def test_invalid_record_fails_schema() -> None:
    with pytest.raises(SchemaValidationError):
        validate_record({"source_id": "x"}, "source-record")


def test_cross_file_ref_resolves() -> None:
    """concept-record.sources $ref to provenance-reference must resolve."""
    with pytest.raises(SchemaValidationError):
        validate_record(
            {
                "concept_id": "c-1",
                "type": "Project",
                "title": "t",
                "sources": [{"resource": "x.md"}],  # missing source_id
            },
            "concept-record",
        )
