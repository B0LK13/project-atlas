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
    """Semantic CI gates are counts/determinism, not absolute wall-clock.

    D-124/D-125: GitHub shared runners measured ~17-18s for the dense 10k
    case. Local reference remains ~4.167s. ``PERFORMANCE_CLASS = MAJOR``.
    ``CI_ABSOLUTE_WALLCLOCK_IS_CORRECTNESS_GATE = NO``. Wall-clock is
    measured and reported; it is not a pass/fail assertion.
    """
    one_k = [_claim(index, groups=200) for index in range(1000)]
    started = time.perf_counter()
    _, one_stats = find_contradiction_candidates_report(one_k)
    one_elapsed = time.perf_counter() - started
    assert one_stats.candidate_count == one_stats.pair_evaluations
    print(f"PERF003_ONE_K_ELAPSED_S={one_elapsed:.6f}")

    dense = [_claim(index, groups=50) for index in range(10000)]
    started = time.perf_counter()
    dense_cands, dense_stats = find_contradiction_candidates_report(dense)
    dense_elapsed = time.perf_counter() - started
    assert dense_stats.candidate_count == 666650
    assert dense_stats.pair_evaluations == 666650
    assert len(dense_cands) == 666650
    assert dense_stats.candidate_count == dense_stats.pair_evaluations
    print(f"PERF003_DENSE_ELAPSED_S={dense_elapsed:.6f}")
    print("PERF003_DENSE_CANDIDATE_COUNT=666650")
    print("PERF003_MATERIALIZED_COUNT=666650")
    print("PERF003_NO_PAIR_DROPPED=YES")
    print("PERF003_PERFORMANCE_CLASS=MAJOR")
    print("CI_ABSOLUTE_WALLCLOCK_IS_CORRECTNESS_GATE=NO")

    distributed = [_claim(index, groups=2000) for index in range(10000)]
    started = time.perf_counter()
    _, dist_stats = find_contradiction_candidates_report(distributed)
    dist_elapsed = time.perf_counter() - started
    assert dist_stats.group_count == 2000
    print(f"PERF003_DISTRIBUTED_ELAPSED_S={dist_elapsed:.6f}")

    wide = [_claim(index, groups=20000) for index in range(100000)]
    started = time.perf_counter()
    empty, wide_stats = find_contradiction_candidates_report(wide, materialize=False)
    wide_elapsed = time.perf_counter() - started
    assert empty == ()
    assert wide_stats.claim_count == 100000
    print(f"PERF003_WIDE_COUNT_ELAPSED_S={wide_elapsed:.6f}")


def test_dense_result_is_deterministic() -> None:
    sample = [_claim(index, groups=50) for index in range(1000)]
    first, first_stats = find_contradiction_candidates_report(sample)
    second, second_stats = find_contradiction_candidates_report(list(reversed(sample)))
    assert first_stats.candidate_count == second_stats.candidate_count
    assert first_stats.pair_evaluations == second_stats.pair_evaluations
    assert [item.candidate_id for item in first] == [item.candidate_id for item in second]
