"""AS-2.0-NEXT-001 — next-action candidate engine."""

from __future__ import annotations

from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ProvenanceReference,
    ReviewState,
)
from project_atlas.intelligence import NEXT_ACTION_CANDIDATE_IS_COMMAND
from project_atlas.intelligence.next_action import (
    NextActionKind,
    propose_next_action_candidates,
)

HASH_A = "a" * 64


def _claim(claim_id: str, *, value: str, source_id: str = "src-a") -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field="datastore",
        value=value,
        provenance=[
            ProvenanceReference(source_id=source_id, resource=f"docs/{source_id}.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_candidates_are_not_commands() -> None:
    assert NEXT_ACTION_CANDIDATE_IS_COMMAND == "NO"
    found = propose_next_action_candidates(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert found
    assert all(item.is_command is False for item in found)
    assert all(item.executable is False for item in found)
    assert all(item.command_flag == "NO" for item in found)
    assert all(item.authority_note == "candidate-not-command" for item in found)
    assert any(item.kind is NextActionKind.REVIEW_CONTRADICTION for item in found)
    dumped = "".join(item.model_dump_json() for item in found)
    assert '"is_command":true' not in dumped.replace(" ", "")
    assert "execute" not in dumped
    assert "merge" not in dumped


def test_empty_project_proposes_unknown_review_not_safe() -> None:
    found = propose_next_action_candidates("harbor-api", [])
    assert found
    assert any(item.kind is NextActionKind.REVIEW_UNKNOWN for item in found)
    assert all(item.is_command is False for item in found)
