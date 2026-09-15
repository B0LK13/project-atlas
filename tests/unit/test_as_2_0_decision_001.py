"""AS-2.0-DECISION-001 — library-only decision candidate model."""

from __future__ import annotations

import pytest

from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ProvenanceReference,
    ReviewState,
)
from project_atlas.intelligence import (
    DECISION_CANDIDATE_IS_COMMAND,
    DECISION_ENGINE_IS_AUTHORITY,
)
from project_atlas.intelligence.decision import (
    ReversibilityClass,
    compose_decision_candidate,
)

HASH_A = "a" * 64


def _claim(
    claim_id: str,
    *,
    value: str,
    field: str = "datastore",
    claim_type: ClaimType = ClaimType.ARCHITECTURE,
    source_id: str = "src-a",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=claim_type,
        field=field,
        value=value,
        provenance=[
            ProvenanceReference(source_id=source_id, resource=f"docs/{source_id}.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_flags_are_not_command_or_authority() -> None:
    assert DECISION_CANDIDATE_IS_COMMAND == "NO"
    assert DECISION_ENGINE_IS_AUTHORITY == "NO"


def test_contested_slot_is_a_candidate_not_a_choice() -> None:
    candidate = compose_decision_candidate(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert candidate.package_id == "AS-2.0-DECISION-001"
    assert candidate.selected is None
    assert candidate.is_command is False
    assert candidate.is_authority is False
    assert candidate.authority_note == "decision-not-authority"
    assert candidate.conflicts
    assert "datastore" in candidate.question
    assert {item.label for item in candidate.options} == {"PostgreSQL 15", "PostgreSQL 16"}
    assert all(item.selected is None for item in candidate.options)
    assert candidate.reversibility is ReversibilityClass.UNKNOWN
    assert "DECISION_ENGINE_IS_AUTHORITY=NO" in candidate.constraints


def test_explicit_question_options_and_reversibility() -> None:
    candidate = compose_decision_candidate(
        "harbor-api",
        [
            _claim(
                "q1",
                value="which datastore should harbor-api use?",
                field="decision_question",
                claim_type=ClaimType.DECISION,
            ),
            _claim("o1", value="PostgreSQL 15", field="decision_option"),
            _claim("o2", value="PostgreSQL 16", field="option", source_id="src-b"),
            _claim("c1", value="must-remain-local-first", field="constraint"),
            _claim("r1", value="reversible", field="reversibility"),
        ],
    )
    assert candidate.question == "which datastore should harbor-api use?"
    assert {item.label for item in candidate.options} == {"PostgreSQL 15", "PostgreSQL 16"}
    assert all(item.source_class == "explicit-option" for item in candidate.options)
    assert "must-remain-local-first" in candidate.constraints
    assert candidate.reversibility is ReversibilityClass.REVERSIBLE
    assert candidate.selected is None


def test_irreversible_only_when_explicit() -> None:
    candidate = compose_decision_candidate(
        "harbor-api",
        [_claim("r1", value="irreversible", field="reversibility")],
    )
    assert candidate.reversibility is ReversibilityClass.IRREVERSIBLE
    assert candidate.selected is None


def test_empty_project_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        compose_decision_candidate("  ", [])
