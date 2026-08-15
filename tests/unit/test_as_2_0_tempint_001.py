"""AS-2.0-TEMPINT-001 — temporal project intelligence."""

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
from project_atlas.intelligence.temporal_intel import (
    TemporalDeltaClass,
    TemporalReasonClass,
    derive_temporal_intelligence,
)
from project_atlas.intelligence.timewin import IntelligenceTimeError
from project_atlas.intelligence.types import AssessableClaim, SourceObservation, ValidityWindowInput

HASH_A = "a" * 64


def _claim(
    claim_id: str,
    *,
    value: str,
    source_id: str = "src-a",
    field: str = "datastore",
    lifecycle: ClaimLifecycle = ClaimLifecycle.NEW,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field=field,
        value=value,
        provenance=[
            ProvenanceReference(source_id=source_id, resource=f"docs/{source_id}.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=lifecycle,
        verification=ReviewState.UNREVIEWED,
    )


def test_new_contradiction_is_not_fabricated_history() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 15")],
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert report.authority_note == "temporal-not-fabricated"
    assert report.package_id == "AS-2.0-TEMPINT-001"
    assert any(item.delta_class is TemporalDeltaClass.BECAME_CONTESTED for item in report.slots)
    assert any(item.reason_class is TemporalReasonClass.NEW_CONTRADICTION for item in report.slots)


def test_stable_slot_is_observation_stable() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 16")],
        [_claim("claim-a", value="PostgreSQL 16")],
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.STABLE
    assert datastore[0].reason_class is TemporalReasonClass.OBSERVATION_TIME


def test_appeared_slot_is_new_evidence() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [],
        [_claim("claim-a", value="PostgreSQL 16")],
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.APPEARED
    assert datastore[0].reason_class is TemporalReasonClass.NEW_EVIDENCE


def test_source_disappearance_is_not_invented_history() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 16")],
        [],
        earlier_sources=(SourceObservation(source_id="src-a", present=True),),
        later_sources=(),
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.DISAPPEARED
    assert datastore[0].reason_class is TemporalReasonClass.SOURCE_DISAPPEARED


def test_became_stale_is_valid_time_not_invalid() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 15")],
        [_claim("claim-a", value="PostgreSQL 15")],
        later_as_of="2026-10-01",
        later_windows=(
            ValidityWindowInput(
                claim_id="claim-a",
                valid_from="2024-01-01",
                valid_to="2024-12-31",
            ),
        ),
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.BECAME_STALE
    assert datastore[0].reason_class is TemporalReasonClass.VALID_TIME


def test_became_unknown_stays_unknown() -> None:
    later = AssessableClaim(
        claim_id="claim-u",
        project_id="harbor-api",
        subject="project:harbor-api",
        field="datastore",
        value="PostgreSQL 15",
        provenance=(),
        confidence=ConfidenceState.UNKNOWN,
    )
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 15")],
        [later],
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.BECAME_UNKNOWN


def test_succession_is_resolved_by_time_not_contest() -> None:
    windows = (
        ValidityWindowInput(
            claim_id="claim-mar",
            valid_from="2024-03-01",
            valid_to="2024-03-31",
        ),
        ValidityWindowInput(
            claim_id="claim-oct",
            valid_from="2024-10-01",
            valid_to="2024-10-31",
        ),
    )
    claims = [
        _claim("claim-mar", value="PostgreSQL 15"),
        _claim("claim-oct", value="PostgreSQL 16", source_id="src-b"),
    ]
    report = derive_temporal_intelligence(
        "harbor-api",
        claims,
        claims,
        earlier_as_of="2024-03-15",
        later_as_of="2024-10-15",
        later_windows=windows,
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.CHANGED
    assert datastore[0].reason_class is TemporalReasonClass.SUCCESSION


def test_same_claim_id_value_change_is_valid_time_when_as_of_present() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 15")],
        [_claim("claim-a", value="PostgreSQL 16")],
        earlier_as_of="2024-03-15",
        later_as_of="2024-10-15",
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.CHANGED
    assert datastore[0].reason_class is TemporalReasonClass.VALID_TIME


def test_same_claim_id_value_change_is_observation_time_without_as_of() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 15")],
        [_claim("claim-a", value="PostgreSQL 16")],
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.CHANGED
    assert datastore[0].reason_class is TemporalReasonClass.OBSERVATION_TIME


def test_new_claim_id_is_new_evidence_change() -> None:
    report = derive_temporal_intelligence(
        "harbor-api",
        [_claim("claim-a", value="PostgreSQL 15")],
        [_claim("claim-b", value="PostgreSQL 16", source_id="src-b")],
    )
    datastore = [item for item in report.slots if item.field == "datastore"]
    assert datastore
    assert datastore[0].delta_class is TemporalDeltaClass.CHANGED
    assert datastore[0].reason_class is TemporalReasonClass.NEW_EVIDENCE


def test_wall_clock_fails_closed() -> None:
    with pytest.raises(IntelligenceTimeError):
        derive_temporal_intelligence("harbor-api", [], [], later_as_of="now")
    with pytest.raises(IntelligenceTimeError):
        derive_temporal_intelligence("harbor-api", [], [], earlier_as_of="today")


def test_empty_project_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        derive_temporal_intelligence("  ", [], [])
