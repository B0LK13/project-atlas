"""Unit tests for JSON schema validation (B-007)."""

from __future__ import annotations

import pytest

from project_atlas.domain import (
    Claim,
    ConceptRecord,
    ConflictRecord,
    ProjectRecord,
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
        "authority-record",
        "claim",
        "claim-alias",
        "claim-lifecycle",
        "concept-record",
        "conflict-record",
        "diagnostic",
        "parser-output",
        "provenance-reference",
        "review-entry",
        "semantic-records",
        "source-record",
        "source-registry",
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
    validate_record(ProjectRecord(project_id="p-1", name="Project"), "semantic-records")


def test_invalid_record_fails_schema() -> None:
    with pytest.raises(SchemaValidationError):
        validate_record({"source_id": "x"}, "source-record")


def test_schema_rejects_unknown_semantic_vocabularies() -> None:
    with pytest.raises(SchemaValidationError):
        validate_record(
            {
                "claim_id": "clm-1",
                "subject": "c-1",
                "claim_type": "future-claim-type",
                "field": "status",
                "value": "active",
                "provenance": [{"source_id": "src-1", "resource": "sources/x.md"}],
                "verification": "unreviewed",
            },
            "claim",
        )
    with pytest.raises(SchemaValidationError):
        validate_record(
            {
                "schema_version": 1,
                "review_id": "review-1",
                "project_id": "p-1",
                "category": "future-review-category",
                "subject_id": "clm-1",
                "reason": "test",
                "source_ids": [],
                "status": "pending",
            },
            "review-entry",
        )
    with pytest.raises(SchemaValidationError):
        validate_record(
            {
                "conflict_id": "conf-1",
                "subject": "c-1",
                "field": "status",
                "claims": [
                    {"source_id": "s-1", "claim": "a"},
                    {"source_id": "s-2", "claim": "b"},
                ],
                "conflict_type": "future-conflict-type",
            },
            "conflict-record",
        )


def test_semantic_schema_rejects_invalid_nested_records() -> None:
    with pytest.raises(SchemaValidationError):
        validate_record(
            {
                "schema_version": 1,
                "project_id": "p-1",
                "name": "Project",
                "generated": True,
                "sources": [
                    {
                        "schema_version": 1,
                        "source_id": "../escape",
                        "path": "README.md",
                        "sha256": None,
                        "lifecycle": "verified",
                        "first_seen": None,
                        "last_seen": None,
                        "previous_sha256": None,
                        "renamed_from": None,
                    }
                ],
                "authority": [],
                "coverage": [],
                "concepts": [],
                "claims": [],
                "agent_events": [],
                "validations": [],
                "decisions": [],
                "relationships": [],
            },
            "semantic-records",
        )


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
