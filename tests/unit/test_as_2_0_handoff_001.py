"""AS-2.0-HANDOFF-001 — evidence-aware handoff intelligence."""

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
from project_atlas.intelligence.handoff import compose_evidence_handoff

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


def test_handoff_is_not_a_command_and_preserves_unknown() -> None:
    handoff = compose_evidence_handoff(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert handoff.authority_note == "handoff-not-command"
    assert handoff.package_id == "AS-2.0-HANDOFF-001"
    assert handoff.what_is_contested
    assert handoff.open_contradictions
    assert "do-not-auto-resolve-contradictions" in handoff.do_not
    assert "do-not-write-canonical-truth" in handoff.do_not
    assert "do-not-mutate-coder-alpha-handoff-packs" in handoff.do_not
    dumped = handoff.model_dump_json()
    assert "healthy" not in dumped


def test_empty_handoff_unknown_is_not_safe() -> None:
    handoff = compose_evidence_handoff("harbor-api", [])
    assert handoff.what_is_unknown or handoff.material_gaps
    assert "do-not-treat-unknown-as-safe" in handoff.do_not
