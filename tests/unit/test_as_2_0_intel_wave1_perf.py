"""Representative scaling for Intelligence Wave 1 pairing.

Contradiction search groups by project/subject/field before pairing.
Dense same-slot groups remain O(k²) inside the slot; that residual is
documented rather than micro-optimized.
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


def _measure(count: int, groups: int) -> tuple[float, int]:
    claims = [_claim(index, groups=groups) for index in range(count)]
    started = time.perf_counter()
    found = find_contradiction_candidates(claims)
    elapsed = time.perf_counter() - started
    return elapsed, len(found)


def test_representative_grouped_pairing_for_1k_and_10k() -> None:
    # Representative Atlas slots are small (a handful of claims per field).
    elapsed_1k, found_1k = _measure(1000, groups=200)
    elapsed_10k, found_10k = _measure(10000, groups=2000)
    assert found_1k > 0
    assert found_10k > found_1k
    assert elapsed_1k < 5.0
    assert elapsed_10k < 15.0
    # 10x more claims with constant group size should stay near-linear.
    assert elapsed_10k < max(elapsed_1k * 25, 15.0)
    state = synthesize_project_state(
        "harbor-api",
        [_claim(index, groups=40) for index in range(200)],
    )
    assert state.project_id == "harbor-api"
