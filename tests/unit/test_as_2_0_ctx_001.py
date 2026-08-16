"""AS-2.0-CTX-001 — derived agent context composer."""

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
from project_atlas.intelligence.agent_context import compose_agent_context
from project_atlas.intelligence.timewin import IntelligenceTimeError

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


def test_context_is_not_authority_and_stays_project_scoped() -> None:
    context = compose_agent_context(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert context.authority_note == "context-not-authority"
    assert context.package_id == "AS-2.0-CTX-001"
    assert context.project_id == "harbor-api"
    assert context.contested_facts
    assert context.contradictions
    assert "DERIVED_INTELLIGENCE_IS_AUTHORITY=NO" in context.constraints
    leaked = compose_agent_context(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            Claim(
                claim_id="other",
                project_id="other-api",
                subject="project:other-api",
                claim_type=ClaimType.ARCHITECTURE,
                field="datastore",
                value="MySQL 8",
                provenance=[
                    ProvenanceReference(source_id="src-z", resource="docs/z.md", sha256=HASH_A)
                ],
                authority=AuthorityLevel.PRIMARY,
                confidence=ConfidenceState.HIGH,
                lifecycle=ClaimLifecycle.NEW,
                verification=ReviewState.UNREVIEWED,
            ),
        ],
    )
    assert all(item.project_id == "harbor-api" for item in leaked.known_facts)
    assert all(item.project_id in {None, "harbor-api"} for item in leaked.contradictions)


def test_empty_project_is_unknown_not_healthy() -> None:
    context = compose_agent_context("harbor-api", [])
    dumped = context.model_dump_json()
    assert "healthy" not in dumped
    assert context.unknown_facts or context.gaps
    assert any(item == "UNKNOWN_IS_VALID=YES" for item in context.constraints)


def test_wall_clock_as_of_fails_closed() -> None:
    with pytest.raises(IntelligenceTimeError):
        compose_agent_context("harbor-api", [], as_of_valid_time="now")
