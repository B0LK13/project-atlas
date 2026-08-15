"""Representative scaling for Intelligence Wave 1 pairing.

Contradiction search must group by project/subject/field before pairing.
This is a measurement test, not a micro-optimization hunt.
"""

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
    synthesize_project_state,
)

HASH_A = "a" * 64


def _claim(index: int, *, groups: int, project: str = "harbor-api") -> Claim:
    group = index % groups
    return Claim(
        claim_id=f"claim-{index:05d}",
        project_id=project,
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field=f"field-{group:03d}",
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


def _measure(count: int, groups: int) -> tuple[float, int]:
    claims = [_claim(index, groups=groups) for index in range(count)]
    started = time.perf_counter()
    found = find_contradiction_candidates(claims)
    elapsed = time.perf_counter() - started
    return elapsed, len(found)


def test_grouped_pairing_scales_past_naive_whole_vault_cost() -> None:
    elapsed_1k, found_1k = _measure(1000, groups=50)
    elapsed_10k, found_10k = _measure(10000, groups=50)
    # Grouped pairing for 10k/50 groups is far below C(10000,2) work.
    # A 40x wall-time blow-up from 1k→10k would indicate accidental N².
    assert elapsed_10k < max(elapsed_1k * 40, 8.0)
    assert found_1k > 0
    assert found_10k > found_1k
    state = synthesize_project_state(
        "harbor-api",
        [_claim(index, groups=20) for index in range(200)],
    )
    assert state.project_id == "harbor-api"
    assert elapsed_1k < 5.0
