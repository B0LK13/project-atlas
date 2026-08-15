"""AS-2.0-INTEL-002 — contradiction candidate intelligence.

Candidates are not proven falsehoods and must not auto-resolve truth.
"""

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
from project_atlas.intelligence import (
    AUTO_RESOLVE_CONTRADICTIONS,
    CONTRADICTION_CANDIDATE_IS_PROVEN_FALSEHOOD,
    ContradictionClass,
    ContradictionContext,
    TemporalRelationship,
    find_contradiction_candidates,
)
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
)
from project_atlas.source_identity import lineage_id

HASH_A = "a" * 64
HASH_B = "b" * 64
PROJECT_UUID = "00000000-0000-4000-8000-000000000001"


def _prov(source_id: str, *, lineage: str | None = None) -> ProvenanceReference:
    return ProvenanceReference(
        source_id=source_id,
        source_lineage_id=lineage,
        project_id="harbor-api",
        resource=f"docs/{source_id}.md",
        sha256=HASH_A,
    )


def _claim(
    claim_id: str,
    *,
    value: str,
    source_id: str = "src-a",
    lineage: str | None = None,
    project_id: str | None = "harbor-api",
    subject: str = "project:harbor-api",
    field: str = "datastore",
    authority: AuthorityLevel = AuthorityLevel.PRIMARY,
    confidence: ConfidenceState = ConfidenceState.HIGH,
    claim_type: ClaimType = ClaimType.ARCHITECTURE,
    authority_domain: str | None = None,
) -> Claim | AssessableClaim:
    claim = Claim(
        claim_id=claim_id,
        project_id=project_id,
        source_lineage_id=lineage,
        subject=subject,
        claim_type=claim_type,
        field=field,
        value=value,
        provenance=[_prov(source_id, lineage=lineage)],
        authority=authority,
        confidence=confidence,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )
    if authority_domain is None:
        return claim
    shaped = AssessableClaim.from_claim(claim)
    return shaped.model_copy(update={"authority_domain": authority_domain})


def test_truth_boundary_forbids_auto_resolve() -> None:
    assert AUTO_RESOLVE_CONTRADICTIONS == "NO"
    assert CONTRADICTION_CANDIDATE_IS_PROVEN_FALSEHOOD == "NO"


def test_incompatible_simultaneous_values_are_value_conflict() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 16"),
            _claim("claim-b", value="PostgreSQL 15", source_id="src-b"),
        ]
    )
    assert len(found) == 1
    assert found[0].candidate_class is ContradictionClass.VALUE_CONFLICT
    assert found[0].claim_a_id == "claim-a"
    assert found[0].claim_b_id == "claim-b"
    assert found[0].authority_note == "candidate-not-resolution"
    assert "auto-resolve-forbidden" in found[0].recommended_human_review_reason


def test_same_value_different_formatting_is_not_a_candidate() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 16"),
            _claim("claim-b", value="  postgresql   16 ", source_id="src-b"),
        ]
    )
    assert found == ()


def test_historical_succession_is_not_a_contradiction() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-mar", value="PostgreSQL 15"),
            _claim("claim-oct", value="PostgreSQL 16", source_id="src-b"),
        ],
        ContradictionContext(
            validity_windows=(
                ValidityWindowInput(
                    claim_id="claim-mar",
                    valid_from="2024-03-01",
                    valid_to="2024-03-31",
                    evidence_kind="document-declared",
                ),
                ValidityWindowInput(
                    claim_id="claim-oct",
                    valid_from="2024-10-01",
                    valid_to="2024-10-31",
                    evidence_kind="document-declared",
                ),
            )
        ),
    )
    assert found == ()


def test_overlapping_validity_is_temporal_conflict() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
        ContradictionContext(
            validity_windows=(
                ValidityWindowInput(
                    claim_id="claim-a",
                    valid_from="2024-01-01",
                    valid_to="2024-12-31",
                ),
                ValidityWindowInput(
                    claim_id="claim-b",
                    valid_from="2024-06-01",
                    valid_to="2025-06-01",
                ),
            )
        ),
    )
    assert len(found) == 1
    assert found[0].candidate_class is ContradictionClass.TEMPORAL_CONFLICT
    assert found[0].temporal_relationship is TemporalRelationship.OVERLAPPING


def test_non_overlapping_validity_is_not_a_contradiction() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
        ContradictionContext(
            validity_windows=(
                ValidityWindowInput(
                    claim_id="claim-a",
                    valid_from="2024-01-01",
                    valid_to="2024-03-31",
                ),
                ValidityWindowInput(
                    claim_id="claim-b",
                    valid_from="2024-04-01",
                    valid_to="2024-12-31",
                ),
            )
        ),
    )
    assert found == ()


def test_same_source_lineage_is_source_divergence() -> None:
    lineage = lineage_id(PROJECT_UUID, "docs/adr.md", HASH_A, 1)
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15", lineage=lineage),
            _claim("claim-b", value="PostgreSQL 16", lineage=lineage, source_id="src-a"),
        ]
    )
    assert len(found) == 1
    assert found[0].candidate_class is ContradictionClass.SOURCE_DIVERGENCE
    assert found[0].source_relationship == "same-lineage"


def test_different_authority_domains_are_not_contradictions() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15", authority_domain="ops"),
            _claim(
                "claim-b",
                value="PostgreSQL 16",
                authority_domain="architecture",
                source_id="src-b",
            ),
        ]
    )
    assert found == ()


def test_different_projects_are_not_contradictions() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15", project_id="harbor-api"),
            _claim("claim-b", value="PostgreSQL 16", project_id="other-proj", source_id="src-b"),
        ]
    )
    assert found == ()


def test_strong_versus_weak_source_is_not_auto_resolved() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 16", authority=AuthorityLevel.PRIMARY),
            _claim(
                "claim-b",
                value="PostgreSQL 15",
                source_id="src-b",
                authority=AuthorityLevel.INFERRED,
            ),
        ]
    )
    assert len(found) == 1
    assert found[0].candidate_class is ContradictionClass.AUTHORITY_CONFLICT
    assert found[0].severity_class.value == "low"
    assert "auto-resolve-forbidden" in found[0].recommended_human_review_reason


def test_unknown_versus_known_is_not_a_contradiction() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 16"),
            _claim(
                "claim-b",
                value="unknown",
                source_id="src-b",
                confidence=ConfidenceState.UNKNOWN,
            ),
        ]
    )
    assert found == ()


def test_missing_source_record_adds_uncertainty() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
        ContradictionContext(
            sources=(
                SourceObservation(source_id="src-a", present=True),
                SourceObservation(source_id="src-b", present=False, deleted=True),
            )
        ),
    )
    assert len(found) == 1
    assert "source-record-missing-or-deleted" in found[0].uncertainty


def test_identity_ambiguity_is_its_own_class() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
        ContradictionContext(identity_ambiguous_claim_ids=("claim-a",)),
    )
    assert len(found) == 1
    assert found[0].candidate_class is ContradictionClass.IDENTITY_AMBIGUITY


def test_replay_and_input_order_do_not_change_semantics() -> None:
    claims_a = [
        _claim("claim-z", value="PostgreSQL 16", source_id="src-z"),
        _claim("claim-a", value="PostgreSQL 15"),
        _claim("claim-m", value="PostgreSQL 14", source_id="src-m"),
    ]
    claims_b = list(reversed(claims_a))
    left = find_contradiction_candidates(claims_a)
    right = find_contradiction_candidates(claims_b)
    assert [item.model_dump() for item in left] == [item.model_dump() for item in right]
    assert [item.candidate_id for item in left] == sorted(item.candidate_id for item in left)
    again = find_contradiction_candidates(claims_a)
    assert [item.model_dump() for item in left] == [item.model_dump() for item in again]


def test_candidates_do_not_mutate_inputs() -> None:
    claims = [
        _claim("claim-a", value="PostgreSQL 15"),
        _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
    ]
    before = [item.model_dump() if isinstance(item, Claim) else item.model_dump() for item in claims]
    find_contradiction_candidates(claims)
    after = [item.model_dump() if isinstance(item, Claim) else item.model_dump() for item in claims]
    assert before == after


def test_grouping_does_not_pair_across_fields() -> None:
    found = find_contradiction_candidates(
        [
            _claim("claim-a", value="PostgreSQL 15", field="datastore"),
            _claim("claim-b", value="active", field="status", source_id="src-b"),
        ]
    )
    assert found == ()
