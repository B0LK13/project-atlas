"""Unit tests for the structured diagnostic model (AS-EXT-001A, directive §7.9)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from project_atlas.domain import (
    CanonicalImpact,
    Diagnostic,
    DiagnosticCode,
    Severity,
    SourceSpan,
)
from project_atlas.schema import validate_record


def _diagnostic(**overrides: object) -> Diagnostic:
    fields: dict[str, object] = {
        "code": DiagnosticCode.UNRESOLVED_LOCATOR,
        "source_path": "docs/evidence/example.yaml",
        "parser": "evidence-yaml",
        "profile": "atlas-receipt",
        "subject": "project-atlas",
        "field": "status",
        "locator": "yamlpath:status",
        "reason": "no stable locator found for recognized claim",
        "remediation": "parse the file with the structured YAML parser",
        "continued": True,
        "canonical_impact": CanonicalImpact.STAGING_ONLY,
    }
    fields.update(overrides)
    return Diagnostic(**fields)  # type: ignore[arg-type]


def test_all_directive_codes_constructible() -> None:
    """§7.9 names twelve diagnostic situations; all are representable."""
    expected = {
        "unresolved-locator",
        "duplicate-locator",
        "ambiguous-identity",
        "duplicate-yaml-key",
        "unknown-receipt-profile",
        "unknown-structured-field",
        "invalid-receipt",
        "unsupported-source-kind",
        "classification-ambiguity",
        "parser-failure",
        "alias-ambiguity",
        "promotion-failure",
    }
    assert {code.value for code in DiagnosticCode} == expected
    for code in DiagnosticCode:
        validate_record(_diagnostic(code=code), "diagnostic")


def test_full_record_validates_against_json_schema() -> None:
    record = _diagnostic(source_span=SourceSpan(start_line=4, end_line=4))
    validate_record(record, "diagnostic")
    assert record.severity is Severity.ERROR


def test_minimal_record_validates() -> None:
    record = Diagnostic(
        code=DiagnosticCode.PROMOTION_FAILURE,
        reason="canonical promotion rolled back",
        continued=True,
    )
    validate_record(record, "diagnostic")
    assert record.canonical_impact is CanonicalImpact.NONE
    assert record.source_span == SourceSpan()


def test_frozen_and_extra_forbidden() -> None:
    record = _diagnostic()
    with pytest.raises(ValidationError):
        record.reason = "rewrite"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _diagnostic(unknown_field="nope")


def test_reason_required() -> None:
    """No silent drop: every diagnostic must state a reason."""
    with pytest.raises(ValidationError):
        _diagnostic(reason="")
    with pytest.raises(ValidationError):
        Diagnostic(code=DiagnosticCode.PARSER_FAILURE, continued=False)  # type: ignore[call-arg]


def test_source_path_traversal_rejected() -> None:
    for unsafe in ("../secret.md", "/abs/path.md", "docs/../../x.md"):
        with pytest.raises(ValidationError, match="within the Vault"):
            _diagnostic(source_path=unsafe)


def test_canonical_impact_vocabulary() -> None:
    assert {item.value for item in CanonicalImpact} == {"none", "staging-only", "blocked"}


def test_continued_flag_records_extraction_continuation() -> None:
    """§7.9/§10: one bad source must not prevent independent extraction."""
    record = _diagnostic(code=DiagnosticCode.PARSER_FAILURE, continued=True)
    assert record.continued is True
    stopped = _diagnostic(code=DiagnosticCode.INVALID_RECEIPT, continued=False)
    assert stopped.continued is False


def test_json_dump_deterministic() -> None:
    first = json.dumps(_diagnostic().model_dump(mode="json"), sort_keys=True)
    second = json.dumps(_diagnostic().model_dump(mode="json"), sort_keys=True)
    assert first == second


def test_schema_rejects_unknown_code() -> None:
    payload = _diagnostic().model_dump(mode="json")
    payload["code"] = "made-up-code"
    with pytest.raises(Exception, match="diagnostic record violates schema"):
        validate_record(payload, "diagnostic")
