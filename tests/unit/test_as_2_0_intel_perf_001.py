"""AS-2.0-INTEL-PERF-001 — dense-group pairing without semantic change."""

from __future__ import annotations

import time

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
    find_contradiction_candidates,
    find_contradiction_candidates_report,
)
from project_atlas.intelligence.contradictions import ContradictionContext
from project_atlas.intelligence.types import ValidityWindowInput

HASH_A = "a" * 64


def _claim(index: int, *, groups: int, project: str = "harbor-api") -> Claim:
    group = index % groups
    return Claim(
        claim_id=f"claim-{index:05d}",
        project_id=project,
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field=f"field-{group:04d}",
        value=f"value-{index % 3}",
        provenance=[
            ProvenanceReference(
                source_id=f"src-{index % 17}",
                resource=f"docs/src-{index % 17}.md",
                sha256=HASH_A,
            )
        ],
        authority=AuthorityLevel.MAINTAINED,
        confidence=ConfidenceState.MEDIUM,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_value_partition_skips_same_value_pairs() -> None:
    claims = [_claim(index, groups=1) for index in range(9)]
    _candidates, stats = find_contradiction_candidates_report(claims)
    # 9 claims, 3 values of 3 → same-value pairs = 3 * C(3,2) = 9
    assert stats.skipped_same_value == 9
    assert stats.pair_evaluations == 3 * 3 * 3  # 3 value-bucket cross products
    assert stats.candidate_count == stats.pair_evaluations


def test_dense_10k_partitions_pairs_and_stays_deterministic() -> None:
    claims = [_claim(index, groups=50) for index in range(10000)]
    started = time.perf_counter()
    left, stats = find_contradiction_candidates_report(claims)
    elapsed = time.perf_counter() - started
    sample = claims[:300]
    first = find_contradiction_candidates(sample)
    second = find_contradiction_candidates(list(reversed(sample)))
    assert [item.candidate_id for item in first] == [item.candidate_id for item in second]
    assert stats.group_count == 50
    naive_pairs = 50 * (200 * 199 // 2)
    assert stats.pair_evaluations < naive_pairs
    assert stats.skipped_same_value > 0
    # Pathological density still materializes many candidates; residual is MAJOR.
    assert elapsed < 20.0
    assert left[0].candidate_id <= left[-1].candidate_id


def test_representative_10k_remains_near_linear() -> None:
    claims = [_claim(index, groups=2000) for index in range(10000)]
    started = time.perf_counter()
    _candidates, stats = find_contradiction_candidates_report(claims)
    elapsed = time.perf_counter() - started
    assert stats.group_count == 2000
    assert elapsed < 2.0
    assert stats.pair_evaluations < 50_000


def test_succession_still_excluded_after_partition() -> None:
    claims = [
        _claim(0, groups=1),
        _claim(1, groups=1),
    ]
    found = find_contradiction_candidates(
        claims,
        ContradictionContext(
            validity_windows=(
                ValidityWindowInput(
                    claim_id="claim-00000",
                    valid_from="2024-01-01",
                    valid_to="2024-03-31",
                ),
                ValidityWindowInput(
                    claim_id="claim-00001",
                    valid_from="2024-04-01",
                    valid_to="2024-12-31",
                ),
            )
        ),
    )
    assert found == ()
