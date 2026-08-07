"""AS-CORE-004 S1: SemanticSubject model, validation, and serialization."""

from __future__ import annotations

import re
import unicodedata

import pytest
from pydantic import ValidationError

from project_atlas.domain import (
    SEMANTIC_SUBJECT_PATTERN,
    SUBJECT_KEY_MAX_LENGTH,
    SemanticSubject,
    SemanticSubjectError,
    SemanticSubjectKind,
    is_semantic_subject_serialized,
    normalize_subject_key,
)
from project_atlas.domain.claims import ID_PATTERN


def test_global_id_pattern_unchanged() -> None:
    """AS-CORE-004: must not widen the global identifier contract."""
    assert ID_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    assert not re.fullmatch(ID_PATTERN, "wp:AS-EXT-001A")
    assert not re.fullmatch(ID_PATTERN, "doc:source-fcb48476ce167a33")


def test_serialize_round_trip_work_package() -> None:
    subject = SemanticSubject.work_package("AS-EXT-001A")
    assert subject.kind is SemanticSubjectKind.WORK_PACKAGE
    assert subject.key == "AS-EXT-001A"
    assert subject.serialize() == "wp:AS-EXT-001A"
    assert SemanticSubject.parse(subject.serialize()) == subject


@pytest.mark.parametrize(
    ("factory", "kind", "key", "serialized"),
    [
        (SemanticSubject.project, SemanticSubjectKind.PROJECT, "project-atlas", "project:project-atlas"),
        (SemanticSubject.adr, SemanticSubjectKind.ADR, "ADR-007", "adr:ADR-007"),
        (
            SemanticSubject.document,
            SemanticSubjectKind.DOCUMENT,
            "source-fcb48476ce167a33",
            "doc:source-fcb48476ce167a33",
        ),
        (SemanticSubject.review, SemanticSubjectKind.REVIEW, "review-001", "review:review-001"),
        (
            SemanticSubject.experiment,
            SemanticSubjectKind.EXPERIMENT,
            "conflict-experiment-001",
            "experiment:conflict-experiment-001",
        ),
        (
            SemanticSubject.roadmap_item,
            SemanticSubjectKind.ROADMAP_ITEM,
            "item-alpha",
            "roadmap-item:item-alpha",
        ),
        (
            SemanticSubject.evidence_entity,
            SemanticSubjectKind.EVIDENCE_ENTITY,
            "receipt-abc",
            "evidence:receipt-abc",
        ),
    ],
)
def test_kind_factories_and_serialization(
    factory: object, kind: SemanticSubjectKind, key: str, serialized: str
) -> None:
    subject = factory(key)  # type: ignore[operator]
    assert subject.kind is kind
    assert subject.key == key
    assert subject.serialize() == serialized
    assert is_semantic_subject_serialized(serialized)
    assert SemanticSubject.parse(serialized) == subject


def test_nfc_equivalence() -> None:
    # U+00E9 (é) vs e + combining acute
    composed = "cafe\u00e9-id"
    decomposed = "cafe\u0065\u0301-id"
    assert composed != decomposed
    assert unicodedata.normalize("NFC", decomposed) == composed
    a = SemanticSubject(kind=SemanticSubjectKind.DOCUMENT, key=composed)
    b = SemanticSubject(kind=SemanticSubjectKind.DOCUMENT, key=decomposed)
    assert a.key == b.key == composed
    assert a.serialize() == b.serialize()


def test_reject_whitespace_and_controls() -> None:
    with pytest.raises(SemanticSubjectError, match="whitespace"):
        normalize_subject_key(" AS-EXT-001A")
    with pytest.raises(SemanticSubjectError, match="whitespace"):
        normalize_subject_key("AS-EXT-001A ")
    with pytest.raises(SemanticSubjectError, match="control"):
        normalize_subject_key("AS-EXT\x001A")
    with pytest.raises(ValidationError):
        SemanticSubject.work_package("AS-EXT\n001A")


def test_reject_path_like_and_colon_in_key() -> None:
    with pytest.raises(SemanticSubjectError, match="path"):
        normalize_subject_key("sources/path/to/file.md")
    with pytest.raises(SemanticSubjectError, match="kind separator"):
        normalize_subject_key("wp:AS-EXT-001A")
    with pytest.raises(ValidationError, match="path"):
        SemanticSubject.document("sources\\imported\\file.md")


def test_reject_empty_oversized_and_bad_charset() -> None:
    with pytest.raises(SemanticSubjectError, match="non-empty"):
        normalize_subject_key("")
    with pytest.raises(SemanticSubjectError, match="max length"):
        normalize_subject_key("a" * (SUBJECT_KEY_MAX_LENGTH + 1))
    with pytest.raises(SemanticSubjectError, match="letters, digits"):
        normalize_subject_key("bad key with spaces")
    with pytest.raises(SemanticSubjectError, match="start with an alphanumeric"):
        normalize_subject_key("-leading-dash")


def test_case_sensitivity_preserved() -> None:
    upper = SemanticSubject.work_package("AS-EXT-001A")
    lower = SemanticSubject.work_package("as-ext-001a")
    assert upper != lower
    assert upper.serialize() != lower.serialize()


def test_parse_rejects_malformed() -> None:
    with pytest.raises(SemanticSubjectError):
        SemanticSubject.parse("project-atlas")
    with pytest.raises(SemanticSubjectError):
        SemanticSubject.parse("unknown:AS-EXT-001A")
    with pytest.raises((SemanticSubjectError, ValidationError)):
        SemanticSubject.parse("wp:")
    with pytest.raises((SemanticSubjectError, ValidationError)):
        SemanticSubject.parse("doc:sources/path/to/file.md")


def test_frozen_and_structured_fields() -> None:
    subject = SemanticSubject.adr("ADR-007")
    with pytest.raises(ValidationError):
        subject.key = "ADR-008"  # type: ignore[misc]
    # Downstream must not need to re-parse opaque strings for meaning.
    assert subject.kind is SemanticSubjectKind.ADR
    assert subject.key == "ADR-007"


def test_semantic_subject_pattern_constant() -> None:
    assert re.fullmatch(SEMANTIC_SUBJECT_PATTERN, "wp:AS-CORE-004")
    assert not re.fullmatch(SEMANTIC_SUBJECT_PATTERN, "project-atlas")
