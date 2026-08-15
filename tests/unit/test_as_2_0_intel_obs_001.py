"""AS-2.0-INTEL-OBS-001 — intelligence run observability."""

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
from project_atlas.intelligence.observe import observe_intelligence_run

HASH_A = "a" * 64


def _claim(claim_id: str, *, value: str) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field="datastore",
        value=value,
        provenance=[
            ProvenanceReference(source_id="src-a", resource="docs/src-a.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_run_report_is_not_a_quality_score() -> None:
    report = observe_intelligence_run(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16"),
        ],
        project_id="harbor-api",
    )
    assert report.authority_note == "obs-not-score"
    assert report.package_id == "AS-2.0-INTEL-OBS-001"
    assert report.claim_count == 2
    assert report.pairing.candidate_count >= 1
    assert report.materialized is False
    dumped = report.model_dump_json()
    assert "healthy" not in dumped
    assert "generated.at" not in dumped
