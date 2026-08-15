"""AS-2.0-INTEL-PERF-003 — compact candidate materialization."""

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
from project_atlas.intelligence.contradictions import find_contradiction_candidates_report

HASH_A = "a" * 64


def _claim(index: int, *, groups: int) -> Claim:
    group = index % groups
    return Claim(
        claim_id=f"claim-{index:05d}",
        project_id="harbor-api",
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


def test_compact_materialize_preserves_counts_and_ids() -> None:
    claims = [_claim(index, groups=8) for index in range(80)]
    built, built_stats = find_contradiction_candidates_report(claims)
    empty, count_stats = find_contradiction_candidates_report(claims, materialize=False)
    assert empty == ()
    assert count_stats.candidate_count == built_stats.candidate_count == len(built)
    assert all(item.authority_note == "candidate-not-resolution" for item in built)
    again, _stats = find_contradiction_candidates_report(list(reversed(claims)))
    assert [item.candidate_id for item in built] == [item.candidate_id for item in again]


def test_dense_and_distributed_benchmarks() -> None:
    one_k = [_claim(index, groups=200) for index in range(1000)]
    started = time.perf_counter()
    _, one_stats = find_contradiction_candidates_report(one_k)
    one_elapsed = time.perf_counter() - started
    assert one_stats.candidate_count == one_stats.pair_evaluations
    assert one_elapsed < 1.0

    dense = [_claim(index, groups=50) for index in range(10000)]
    started = time.perf_counter()
    dense_cands, dense_stats = find_contradiction_candidates_report(dense)
    dense_elapsed = time.perf_counter() - started
    assert dense_stats.candidate_count == 666650
    assert len(dense_cands) == 666650
    # Meaningful improvement over the Wave-8 8.8s residual.
    assert dense_elapsed < 6.5

    distributed = [_claim(index, groups=2000) for index in range(10000)]
    started = time.perf_counter()
    _, dist_stats = find_contradiction_candidates_report(distributed)
    dist_elapsed = time.perf_counter() - started
    assert dist_stats.group_count == 2000
    assert dist_elapsed < 3.0

    wide = [_claim(index, groups=20000) for index in range(100000)]
    started = time.perf_counter()
    empty, wide_stats = find_contradiction_candidates_report(wide, materialize=False)
    wide_elapsed = time.perf_counter() - started
    assert empty == ()
    assert wide_stats.claim_count == 100000
    assert wide_elapsed < 15.0
