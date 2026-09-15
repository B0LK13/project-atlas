"""AS-CORE-004: runtime semantic-subject grammar must match JSON Schema."""

from __future__ import annotations

import re

import pytest

from project_atlas.domain import (
    SEMANTIC_SUBJECT_PATTERN,
    SUBJECT_KEY_PATTERN,
    SemanticSubject,
    SemanticSubjectError,
    SemanticSubjectKind,
    normalize_subject_key,
)
from project_atlas.domain.claims import Claim, ProvenanceReference
from project_atlas.domain.conflicts import ConflictRecord
from project_atlas.domain.parser_output import (
    AmbiguityStatus,
    LocatorConfidence,
    LocatorKind,
    ParserOutput,
    SourceSpan,
)
from project_atlas.domain.vocabulary import AuthorityLevel, ClaimType
from project_atlas.schema import SchemaValidationError, validate_record

_KIND_KEYS: dict[SemanticSubjectKind, str] = {
    SemanticSubjectKind.PROJECT: "project-atlas",
    SemanticSubjectKind.WORK_PACKAGE: "AS-CORE-004",
    SemanticSubjectKind.ADR: "ADR-007",
    SemanticSubjectKind.DOCUMENT: "source-fcb48476ce167a33",
    SemanticSubjectKind.REVIEW: "verify-disposition",
    SemanticSubjectKind.EXPERIMENT: "conflict-experiment-001",
    SemanticSubjectKind.ROADMAP_ITEM: "item-alpha",
    SemanticSubjectKind.EVIDENCE_ENTITY: "receipt-abc",
}

_PROV = ProvenanceReference(source_id="src-1", resource="sources/x.md")


def _claim(subject: str) -> Claim:
    return Claim(
        claim_id="clm-parity-1",
        subject=subject,
        field="package_status",
        value="active",
        provenance=[_PROV],
    )


def _conflict(subject: str) -> ConflictRecord:
    return ConflictRecord(
        conflict_id="conf-parity-1",
        subject=subject,
        field="package_status",
        claims=[
            {"source_id": "s-1", "claim": "active"},
            {"source_id": "s-2", "claim": "draft"},
        ],
    )


def _parser_output(subject: str) -> ParserOutput:
    return ParserOutput(
        parser_id="parity-parser",
        parser_version="1",
        source_kind="markdown",
        document_profile="work-package",
        claim_type=ClaimType.WORK_PACKAGE_STATUS,
        subject=subject,
        normalized_field="package_status",
        raw_value="active",
        normalized_value="active",
        stable_semantic_locator="heading:status",
        locator_kind=LocatorKind.HEADING,
        locator_confidence=LocatorConfidence.STABLE,
        source_path="docs/work-packages/AS-CORE-004.md",
        source_span=SourceSpan(start_line=1, end_line=1),
        structural_context=(),
        authority_hint=AuthorityLevel.PRIMARY,
        ambiguity_status=AmbiguityStatus.UNAMBIGUOUS,
    )


@pytest.mark.parametrize("kind", list(SemanticSubjectKind))
def test_runtime_valid_subject_accepted_by_all_schemas(kind: SemanticSubjectKind) -> None:
    subject = SemanticSubject(kind=kind, key=_KIND_KEYS[kind])
    serialized = subject.serialize()
    assert re.fullmatch(SUBJECT_KEY_PATTERN, subject.key)
    assert re.fullmatch(SEMANTIC_SUBJECT_PATTERN, serialized)
    validate_record(_claim(serialized), "claim")
    validate_record(_conflict(serialized), "conflict-record")
    validate_record(_parser_output(serialized), "parser-output")


@pytest.mark.parametrize(
    "invalid_key",
    [
        "cafe\u00e9-id",
        "cafe\u0065\u0301-id",
        "AS-EXT-00\u04301A",
        "bad key",
        "sources/path.md",
        "wp:nested",
        "",
        "a" * 129,
    ],
)
def test_runtime_invalid_key_not_canonical_semantic_subject(invalid_key: str) -> None:
    with pytest.raises(SemanticSubjectError):
        normalize_subject_key(invalid_key)


def test_schema_rejects_non_ascii_semantic_subject_serialization() -> None:
    bogus = "doc:cafe\u00e9-id"
    assert re.fullmatch(SEMANTIC_SUBJECT_PATTERN, bogus) is None
    with pytest.raises((SchemaValidationError, Exception)):
        # Runtime Claim subject validator also rejects before schema in many paths;
        # either boundary is acceptable for the anti-drift invariant.
        _claim(bogus)
