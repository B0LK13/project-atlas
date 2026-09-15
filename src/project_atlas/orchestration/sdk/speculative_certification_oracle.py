"""External governor oracle for speculative certification — independent of IUT persistence.

MODULE_RESULT != CERTIFICATION_AUTHORITY. The oracle recomputes expected terminal
state from seal pins + lane receipts without reading module durable files as truth.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from project_atlas.orchestration.sdk.speculative_certification import (
    CertificationState,
    LaneReceipt,
    LaneResult,
)


@dataclass(frozen=True, slots=True)
class OracleExpectation:
    generation: int
    head: str
    tree: str
    base_main: str
    required_lanes: tuple[str, ...]
    state: CertificationState
    new_p0: int
    new_p1: int
    previous_p1_reopened: int
    exact_pin_evidence_promoted: bool
    certification_frozen: bool
    merge_authorization: str
    lane_results: dict[str, LaneResult]


def oracle_evaluate(
    *,
    generation: int,
    head: str,
    tree: str,
    base_main: str,
    required_lanes: Sequence[str],
    receipts: Sequence[LaneReceipt],
    live_head: str | None = None,
    live_tree: str | None = None,
    live_main: str | None = None,
    tip_drift: bool = False,
    promote: bool = False,
) -> OracleExpectation:
    """Compute expected barrier state independently of durable module files."""
    lanes = {name: LaneResult.PENDING for name in required_lanes}
    p0 = p1 = prev = 0
    for receipt in receipts:
        if receipt.generation != generation:
            continue
        if receipt.lane not in lanes:
            continue
        if receipt.head != head or receipt.tree != tree:
            continue
        # First terminal wins; ignore later conflicts (oracle mirrors fail-closed).
        if lanes[receipt.lane] != LaneResult.PENDING:
            continue
        if receipt.result == LaneResult.PENDING:
            continue
        lanes[receipt.lane] = receipt.result
        p0 += receipt.new_p0
        p1 += receipt.new_p1
        prev += receipt.previous_p1_reopened

    if tip_drift or (
        live_head is not None
        and live_tree is not None
        and (live_head != head or live_tree != tree)
    ):
        return OracleExpectation(
            generation=generation,
            head=head,
            tree=tree,
            base_main=base_main,
            required_lanes=tuple(required_lanes),
            state=CertificationState.CANCELLED_TIP_DRIFT,
            new_p0=p0,
            new_p1=p1,
            previous_p1_reopened=prev,
            exact_pin_evidence_promoted=False,
            certification_frozen=False,
            merge_authorization="NOT_GRANTED",
            lane_results=lanes,
        )

    if any(result == LaneResult.PENDING for result in lanes.values()):
        state = (
            CertificationState.CANDIDATE_SEALED
            if all(result == LaneResult.PENDING for result in lanes.values())
            else CertificationState.BARRIER_OPEN
        )
        return OracleExpectation(
            generation=generation,
            head=head,
            tree=tree,
            base_main=base_main,
            required_lanes=tuple(required_lanes),
            state=state,
            new_p0=p0,
            new_p1=p1,
            previous_p1_reopened=prev,
            exact_pin_evidence_promoted=False,
            certification_frozen=False,
            merge_authorization="NOT_GRANTED",
            lane_results=lanes,
        )

    failed = any(result == LaneResult.FAIL for result in lanes.values()) or p0 or p1 or prev
    if failed:
        state = CertificationState.BARRIER_FAILED
        promoted = False
        frozen = False
    else:
        state = CertificationState.CERTIFIED
        promoted = False
        frozen = False
        if promote:
            if live_main is not None and live_main != base_main:
                # target moved — promotion illegal; remain CERTIFIED without promote
                pass
            elif live_head == head and live_tree == tree and (
                live_main is None or live_main == base_main
            ):
                state = CertificationState.EVIDENCE_PROMOTED
                promoted = True
                frozen = True

    return OracleExpectation(
        generation=generation,
        head=head,
        tree=tree,
        base_main=base_main,
        required_lanes=tuple(required_lanes),
        state=state,
        new_p0=p0,
        new_p1=p1,
        previous_p1_reopened=prev,
        exact_pin_evidence_promoted=promoted,
        certification_frozen=frozen,
        merge_authorization="NOT_GRANTED",
        lane_results=lanes,
    )


def assert_oracle_parity(
    *,
    barrier_state: CertificationState,
    barrier_p0: int,
    barrier_p1: int,
    barrier_prev: int,
    barrier_promoted: bool,
    barrier_frozen: bool,
    barrier_merge: str,
    expectation: OracleExpectation,
) -> None:
    if barrier_state != expectation.state:
        raise AssertionError(
            f"oracle state mismatch: module={barrier_state} oracle={expectation.state}"
        )
    if (
        barrier_p0 != expectation.new_p0
        or barrier_p1 != expectation.new_p1
        or barrier_prev != expectation.previous_p1_reopened
    ):
        raise AssertionError("oracle P0/P1 mismatch")
    if barrier_promoted != expectation.exact_pin_evidence_promoted:
        raise AssertionError("oracle promotion mismatch")
    if barrier_frozen != expectation.certification_frozen:
        raise AssertionError("oracle freeze mismatch")
    if barrier_merge != "NOT_GRANTED" or expectation.merge_authorization != "NOT_GRANTED":
        raise AssertionError("oracle merge-authority isolation failed")
