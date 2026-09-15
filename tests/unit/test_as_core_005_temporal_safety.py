"""AS-CORE-005 structural safety: supersession graph, fail-closed, no latest-wins."""

from __future__ import annotations

from project_atlas.domain.temporal import ResolutionBasis, TemporalStatus
from project_atlas.domain.vocabulary import AuthorityLevel
from project_atlas.temporal_evaluator import evaluate_group
from project_atlas.temporal_evidence import ClaimTemporalContext, SourceTemporalFacts


def _ctx(
    claim_id: str,
    *,
    subject: str = "wp:X",
    field: str = "package_status",
    value: str = "v",
    source_id: str = "source-a",
    authority: str = AuthorityLevel.VALIDATED_EXECUTION.value,
    facts: SourceTemporalFacts | None = None,
) -> ClaimTemporalContext:
    return ClaimTemporalContext(
        claim_id=claim_id,
        subject=subject,
        field=field,
        value=value,
        source_id=source_id,
        authority=authority,
        facts=facts or SourceTemporalFacts(source_id=source_id, path=f"docs/{source_id}.yaml"),
        path=f"docs/{source_id}.yaml",
    )


def test_direct_lifecycle_supersession() -> None:
    earlier = _ctx(
        "claim-earlier",
        value="certified",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/post-merge.yaml",
            original_certification="abc",
            status_value="certified",
        ),
    )
    later = _ctx(
        "claim-later",
        value="recertified-merge-eligible",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/recert.yaml",
            original_certification="abc",
            status_value="recertified-merge-eligible",
            has_post_merge_signal=True,
        ),
    )
    result = evaluate_group([earlier, later], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.CURRENT
    assert result.disposition.current_claim_id == "claim-later"
    assert "claim-earlier" in result.disposition.historical_claim_ids
    assert result.disposition.resolution_basis is ResolutionBasis.LIFECYCLE_PAIR
    assert result.conflict_reclassified is True


def test_chained_candidate_supersession() -> None:
    c3 = _ctx(
        "claim-c3",
        value="implementation-complete",
        source_id="source-c3",
        facts=SourceTemporalFacts(
            source_id="source-c3",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            supersedes_tokens=(),
            status_value="implementation-complete",
        ),
    )
    c4 = _ctx(
        "claim-c4",
        value="implementation-complete-pending-certification",
        source_id="source-c4",
        facts=SourceTemporalFacts(
            source_id="source-c4",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            supersedes_tokens=("V2-003",),
            status_value="implementation-complete-pending-certification",
        ),
    )
    c5 = _ctx(
        "claim-c5",
        value="local-validation-complete-pending-isolated-review",
        source_id="source-c5",
        facts=SourceTemporalFacts(
            source_id="source-c5",
            path="docs/evidence/AS-CORE-003-v2-candidate-005.yaml",
            candidate_ordinal=5,
            supersedes_tokens=("V2-004",),
            status_value="local-validation-complete-pending-isolated-review",
        ),
    )
    result = evaluate_group([c3, c4, c5], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.CURRENT
    assert result.disposition.current_claim_id == "claim-c5"
    assert set(result.disposition.historical_claim_ids) == {"claim-c3", "claim-c4"}


def test_duplicate_reobservation_with_plan_id() -> None:
    durable_a = _ctx(
        "claim-da",
        field="work-package",
        value="AS-CORE-003",
        source_id="source-da",
        facts=SourceTemporalFacts(
            source_id="source-da",
            path="docs/evidence/receipt-a.yaml",
            work_package_value="AS-CORE-003",
            status_value="implementation-complete",
        ),
    )
    durable_b = _ctx(
        "claim-db",
        field="work-package",
        value="AS-CORE-003",
        source_id="source-db",
        facts=SourceTemporalFacts(
            source_id="source-db",
            path="docs/evidence/receipt-b.yaml",
            work_package_value="AS-CORE-003",
            status_value="implementation-complete",
        ),
    )
    planned = _ctx(
        "claim-plan",
        field="work-package",
        value="AS-CORE-003-A",
        source_id="source-plan",
        facts=SourceTemporalFacts(
            source_id="source-plan",
            path="docs/evidence/AS-CORE-003-claim-identity-amendment-plan.yaml",
            work_package_value="AS-CORE-003-A",
            status_value="Planned",
        ),
    )
    result = evaluate_group(
        [durable_a, durable_b, planned],
        project_id="project-atlas",
        compilation_id="c1",
    )
    assert result.disposition.temporal_status is TemporalStatus.CURRENT
    assert result.disposition.current_claim_id in {"claim-da", "claim-db"}
    assert "claim-plan" in result.disposition.historical_claim_ids
    assert result.disposition.resolution_basis is ResolutionBasis.REOBSERVATION


def test_authority_dependent_title_pending() -> None:
    a = _ctx(
        "claim-t1",
        subject="wp:AS-ID-001",
        field="title",
        value="Receipt Title A",
    )
    b = _ctx(
        "claim-t2",
        subject="wp:AS-ID-001",
        field="title",
        value="Work Package Title B",
        source_id="source-newer",
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.AUTHORITY_PENDING
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.TITLE_COLLAPSE
    assert "newest observation does not imply current truth" in result.disposition.rationale


def test_latest_wins_rejection() -> None:
    older = _ctx("claim-o", value="correct")
    newer = _ctx(
        "claim-n",
        value="wrong-but-newer",
        source_id="source-newer",
        facts=SourceTemporalFacts(
            source_id="source-newer",
            path="docs/evidence/newer.yaml",
            document_timestamp=__import__("datetime").datetime(2026, 12, 1),
            status_value="wrong-but-newer",
        ),
    )
    result = evaluate_group([older, newer], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.current_claim_id is None
    assert result.disposition.temporal_status in {
        TemporalStatus.UNRESOLVED,
        TemporalStatus.AUTHORITY_PENDING,
    }
    assert result.conflict_reclassified is False


def test_self_supersession_rejected() -> None:
    a = _ctx(
        "claim-a",
        value="v1",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            supersedes_tokens=("V2-003",),
            status_value="v1",
        ),
    )
    b = _ctx(
        "claim-b",
        value="v2",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            supersedes_tokens=("V2-003",),
            status_value="v2",
        ),
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.resolution_basis is ResolutionBasis.MALFORMED
    assert result.disposition.current_claim_id is None


def test_cycle_fail_closed() -> None:
    a = _ctx(
        "claim-a",
        value="v1",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            supersedes_tokens=("V2-004",),
            status_value="v1",
        ),
    )
    b = _ctx(
        "claim-b",
        value="v2",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            supersedes_tokens=("V2-003",),
            status_value="v2",
        ),
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.CYCLIC


def test_branching_successors_fail_closed() -> None:
    base = _ctx(
        "claim-base",
        value="v0",
        facts=SourceTemporalFacts(
            source_id="source-base",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            status_value="v0",
        ),
    )
    b = _ctx(
        "claim-b",
        value="v2",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-CORE-003-v2-candidate-005.yaml",
            candidate_ordinal=5,
            supersedes_tokens=("V2-003",),
            status_value="v2",
        ),
    )
    c = _ctx(
        "claim-c",
        value="v3",
        source_id="source-c",
        facts=SourceTemporalFacts(
            source_id="source-c",
            path="docs/evidence/AS-CORE-003-v2-candidate-006.yaml",
            candidate_ordinal=6,
            supersedes_tokens=("V2-003",),
            status_value="v3",
        ),
    )
    result = evaluate_group([base, b, c], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.BRANCHING


def test_dangling_supersedes_fail_closed() -> None:
    """Verifier reproduction: unbound supersedes token must not tip current.

    On 251f9b79496e03bf38a8a7fcebd37b2b9ec0ab9f this incorrectly returned
    current/supersedes via soft ordinal ranking. After remediation: dangling.
    """
    a = _ctx(
        "claim-a",
        value="v1",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            status_value="v1",
        ),
    )
    b = _ctx(
        "claim-b",
        value="v2",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            supersedes_tokens=("V2-099",),  # dangling — no such candidate in group
            status_value="v2",
        ),
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.DANGLING
    assert result.conflict_reclassified is False
    assert "V2-099" in result.disposition.rationale
    assert "supersedes:" in result.disposition.rationale


def test_dangling_superseded_by_fail_closed() -> None:
    a = _ctx(
        "claim-a",
        value="v1",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            superseded_by_token="V2-099",
            status_value="v1",
        ),
    )
    b = _ctx(
        "claim-b",
        value="v2",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            status_value="v2",
        ),
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.DANGLING
    assert "superseded_by:" in result.disposition.rationale
    assert "V2-099" in result.disposition.rationale


def test_no_temporal_evidence_remains_unresolved() -> None:
    a = _ctx(
        "claim-a",
        value="v1",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            status_value="v1",
        ),
    )
    b = _ctx(
        "claim-b",
        value="v2",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            status_value="v2",
        ),
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.UNRESOLVED_AMBIGUOUS


def test_valid_chain_plus_material_dangling_tip_fail_closed() -> None:
    """Bound edge 4→3 plus unbound tip 5 (V2-099 only) → no unique tip."""
    c3 = _ctx(
        "claim-c3",
        value="v3",
        source_id="s3",
        facts=SourceTemporalFacts(
            source_id="s3",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            status_value="v3",
        ),
    )
    c4 = _ctx(
        "claim-c4",
        value="v4",
        source_id="s4",
        facts=SourceTemporalFacts(
            source_id="s4",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            supersedes_tokens=("V2-003",),
            status_value="v4",
        ),
    )
    c5 = _ctx(
        "claim-c5",
        value="v5",
        source_id="s5",
        facts=SourceTemporalFacts(
            source_id="s5",
            path="docs/evidence/AS-CORE-003-v2-candidate-005.yaml",
            candidate_ordinal=5,
            supersedes_tokens=("V2-099",),
            status_value="v5",
        ),
    )
    result = evaluate_group([c3, c4, c5], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis in {
        ResolutionBasis.BRANCHING,
        ResolutionBasis.DANGLING,
        ResolutionBasis.UNRESOLVED_AMBIGUOUS,
    }


def test_bound_chain_with_out_of_group_historical_token_still_resolves() -> None:
    """Out-of-group token (V2-001) is irrelevant once bound in-group tip is unique."""
    c3 = _ctx(
        "claim-c3",
        value="v3",
        source_id="s3",
        facts=SourceTemporalFacts(
            source_id="s3",
            path="docs/evidence/AS-CORE-003-v2-candidate-003.yaml",
            candidate_ordinal=3,
            supersedes_tokens=("V2-001",),  # not in this conflict group
            status_value="v3",
        ),
    )
    c4 = _ctx(
        "claim-c4",
        value="v4",
        source_id="s4",
        facts=SourceTemporalFacts(
            source_id="s4",
            path="docs/evidence/AS-CORE-003-v2-candidate-004.yaml",
            candidate_ordinal=4,
            supersedes_tokens=("V2-003",),
            status_value="v4",
        ),
    )
    c5 = _ctx(
        "claim-c5",
        value="v5",
        source_id="s5",
        facts=SourceTemporalFacts(
            source_id="s5",
            path="docs/evidence/AS-CORE-003-v2-candidate-005.yaml",
            candidate_ordinal=5,
            supersedes_tokens=("V2-004",),
            status_value="v5",
        ),
    )
    result = evaluate_group([c3, c4, c5], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.CURRENT
    assert result.disposition.current_claim_id == "claim-c5"
    assert set(result.disposition.historical_claim_ids) == {"claim-c3", "claim-c4"}


def test_same_source_multi_value_unresolved() -> None:
    a = _ctx(
        "claim-a",
        subject="doc:source-plan",
        field="roadmap",
        value="row-1",
        source_id="source-plan",
    )
    b = _ctx(
        "claim-b",
        subject="doc:source-plan",
        field="roadmap",
        value="row-2",
        source_id="source-plan",
    )
    result = evaluate_group([a, b], project_id="project-atlas", compilation_id="c1")
    assert result.disposition.temporal_status is TemporalStatus.UNRESOLVED
    assert result.disposition.current_claim_id is None
    assert result.disposition.resolution_basis is ResolutionBasis.UNRESOLVED_SAME_SOURCE_MULTI


def test_claims_remain_immutable_after_evaluation() -> None:
    earlier = _ctx(
        "claim-earlier",
        value="certified-merge-eligible",
        facts=SourceTemporalFacts(
            source_id="source-a",
            path="docs/evidence/AS-RET-001-receipt.yaml",
            status_value="certified-merge-eligible",
        ),
    )
    later = _ctx(
        "claim-later",
        value="merged-and-post-merge-validated",
        source_id="source-b",
        facts=SourceTemporalFacts(
            source_id="source-b",
            path="docs/evidence/AS-RET-001-post-merge-receipt.yaml",
            status_value="merged-and-post-merge-validated",
            has_post_merge_signal=True,
            merged_to_main_at=__import__("datetime").datetime(2026, 6, 1),
        ),
    )
    before = (earlier.value, later.value)
    result = evaluate_group([earlier, later], project_id="project-atlas", compilation_id="c1")
    assert (earlier.value, later.value) == before
    assert result.disposition.temporal_status is TemporalStatus.CURRENT
    assert result.disposition.current_claim_id == "claim-later"
