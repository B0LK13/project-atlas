"""AS-2.0-RISK-001 — attention / risk signals."""

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
from project_atlas.intelligence.risk import RiskClass, detect_risk_signals

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


def test_risk_is_not_fact_and_has_reason() -> None:
    signals = detect_risk_signals(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert signals
    assert all(item.authority_note == "risk-not-fact" for item in signals)
    assert all(item.reason for item in signals)
    assert any(item.risk_class is RiskClass.ATTENTION for item in signals)
    dumped = "".join(item.model_dump_json() for item in signals)
    assert "failure" not in dumped
    assert "healthy" not in dumped


def test_empty_project_unknown_is_not_safe() -> None:
    signals = detect_risk_signals("harbor-api", [])
    assert any("not-safe" in item.reason for item in signals)
    assert any(item.risk_class is RiskClass.UNKNOWN for item in signals)
