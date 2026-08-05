"""Unit tests for the parser output contract (AS-EXT-001A, directive §7.2)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from project_atlas.domain import (
    AmbiguityStatus,
    AuthorityLevel,
    ClaimType,
    LocatorConfidence,
    LocatorKind,
    ParserOutput,
    SourceSpan,
)
from project_atlas.schema import validate_record


def _record(**overrides: object) -> ParserOutput:
    fields: dict[str, object] = {
        "parser_id": "evidence-yaml",
        "parser_version": "1.0.0",
        "source_kind": "evidence-yaml",
        "document_profile": "atlas-core-receipt",
        "claim_type": ClaimType.WORK_PACKAGE_STATUS,
        "subject": "project-atlas",
        "normalized_field": "status",
        "raw_value": "status: certified",
        "normalized_value": "certified",
        "stable_semantic_locator": "yamlpath:status",
        "locator_kind": LocatorKind.YAMLPATH,
        "source_path": "docs/evidence/example.yaml",
    }
    fields.update(overrides)
    return ParserOutput(**fields)  # type: ignore[arg-type]


def test_minimal_record_validates_against_json_schema() -> None:
    record = _record()
    validate_record(record, "parser-output")


def test_frozen_model_rejects_mutation() -> None:
    record = _record()
    with pytest.raises(ValidationError):
        record.normalized_value = "superseded"  # type: ignore[misc]


def test_no_claim_identity_fields_accepted() -> None:
    """§7.2: parser output must not calculate final claim identity."""
    for forbidden in ("claim_id", "identity_key", "v2_claim_id"):
        with pytest.raises(ValidationError):
            _record(**{forbidden: "claim-abc123"})


def test_unknown_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(unexpected_field="nope")


def test_source_span_end_must_not_precede_start() -> None:
    with pytest.raises(ValidationError, match="end_line"):
        SourceSpan(start_line=10, end_line=3)


def test_source_span_lines_are_one_based() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(start_line=0)
    span = SourceSpan(start_line=1, end_line=1)
    assert span.start_line == 1


def test_source_path_traversal_rejected() -> None:
    for unsafe in ("../secret.yaml", "docs/../../etc/passwd", "/abs/path.yaml"):
        with pytest.raises(ValidationError, match="within the Vault"):
            _record(source_path=unsafe)


def test_subject_and_parser_id_patterns() -> None:
    with pytest.raises(ValidationError):
        _record(subject="has spaces")
    with pytest.raises(ValidationError):
        _record(parser_id="-leading-dash")
    # Dotted structural subjects (e.g. verify_disposition.status) are valid.
    record = _record(subject="verify_disposition.status")
    assert record.subject == "verify_disposition.status"


def test_defaults_applied() -> None:
    record = _record()
    assert record.schema_version == 1
    assert record.locator_confidence is LocatorConfidence.STABLE
    assert record.authority_hint is AuthorityLevel.INFERRED
    assert record.ambiguity_status is AmbiguityStatus.UNAMBIGUOUS
    assert record.structural_context == ()
    assert record.source_span == SourceSpan()


def test_structural_context_order_preserved() -> None:
    record = _record(
        structural_context=("verify_disposition", "status"),
        locator_kind=LocatorKind.BLOCK_SCOPED_KEY,
    )
    assert record.structural_context == ("verify_disposition", "status")


def test_provisional_locator_confidence_for_indexed_sequences() -> None:
    """§7.4: numeric sequence indexes are provisional only."""
    record = _record(
        stable_semantic_locator="yamlpath:validation_runs[0].outcome",
        locator_confidence=LocatorConfidence.PROVISIONAL,
    )
    validate_record(record, "parser-output")
    assert record.locator_confidence is LocatorConfidence.PROVISIONAL


def test_withheld_record_carries_best_candidate_locator() -> None:
    """§7.7: withheld claims stay visible with diagnostics-grade metadata."""
    record = _record(
        ambiguity_status=AmbiguityStatus.WITHHELD,
        locator_kind=LocatorKind.HEADING,
        stable_semantic_locator="heading:nebula-control-platform",
    )
    validate_record(record, "parser-output")
    assert record.ambiguity_status is AmbiguityStatus.WITHHELD


def test_json_dump_deterministic() -> None:
    record = _record(source_span=SourceSpan(start_line=4, end_line=4))
    twin = _record(source_span=SourceSpan(start_line=4, end_line=4))
    first = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    second = json.dumps(twin.model_dump(mode="json"), sort_keys=True)
    assert first == second


def test_schema_rejects_missing_required_field() -> None:
    payload = _record().model_dump(mode="json")
    del payload["stable_semantic_locator"]
    with pytest.raises(Exception, match="parser-output record violates schema"):
        validate_record(payload, "parser-output")
