"""Unit tests for AS-ORCH-SPECULATIVE-CERTIFICATION-001 durable seal/barrier."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.models import SdkRuntimeError
from project_atlas.orchestration.sdk.speculative_certification import (
    REQUIRED_LANES,
    CertificationState,
    LaneReceipt,
    LaneResult,
    cancel_for_tip_drift,
    evaluate_barrier,
    load_barrier,
    promote_exact_pin_evidence,
    record_lane_result,
    seal_candidate,
)

HEAD = "2c81c6d61c981b346968d022c88d985e5e86673a"
TREE = "43befdb707cf0455572242ca3a1d1b87f71050ce"
MAIN = "7e797468a2eca37c959920912b1fa264df4be638"
OTHER = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _pass_all(root: Path) -> None:
    for lane in REQUIRED_LANES:
        record_lane_result(
            root,
            LaneReceipt(
                lane=lane,
                result=LaneResult.PASS,
                head=HEAD,
                tree=TREE,
            ),
        )


def test_seal_and_promote_exact_pin(tmp_path: Path) -> None:
    seal = seal_candidate(
        tmp_path, generation=107, head=HEAD, tree=TREE, base_main=MAIN
    )
    assert seal.merge_authorization == "NOT_GRANTED"
    _pass_all(tmp_path)
    barrier = evaluate_barrier(tmp_path)
    assert barrier.state == CertificationState.CERTIFIED
    promoted = promote_exact_pin_evidence(
        tmp_path, live_head=HEAD, live_tree=TREE, live_main=MAIN
    )
    assert promoted.exact_pin_evidence_promoted is True
    assert promoted.certification_frozen is True
    assert promoted.merge_authorization == "NOT_GRANTED"
    assert (tmp_path / ".atlas/orchestration/sdk-runtime/speculative-cert/exact-pin-evidence-promoted.json").is_file()


def test_lane_pin_mismatch_rejected(tmp_path: Path) -> None:
    seal_candidate(tmp_path, generation=1, head=HEAD, tree=TREE, base_main=MAIN)
    with pytest.raises(SdkRuntimeError) as exc:
        record_lane_result(
            tmp_path,
            LaneReceipt(
                lane="CI",
                result=LaneResult.PASS,
                head=OTHER,
                tree=TREE,
            ),
        )
    assert exc.value.code == "SPECULATIVE_CERT_PIN_MISMATCH"


def test_tip_drift_cancels_and_blocks_promotion(tmp_path: Path) -> None:
    seal_candidate(tmp_path, generation=2, head=HEAD, tree=TREE, base_main=MAIN)
    _pass_all(tmp_path)
    evaluate_barrier(tmp_path)
    cancelled = cancel_for_tip_drift(tmp_path, live_head=OTHER, live_tree=TREE)
    assert cancelled.state == CertificationState.CANCELLED_TIP_DRIFT
    drifted = promote_exact_pin_evidence(
        tmp_path, live_head=OTHER, live_tree=TREE, live_main=MAIN
    )
    assert drifted.state == CertificationState.CANCELLED_TIP_DRIFT
    assert drifted.exact_pin_evidence_promoted is False


def test_target_moved_blocks_promotion(tmp_path: Path) -> None:
    seal_candidate(tmp_path, generation=3, head=HEAD, tree=TREE, base_main=MAIN)
    _pass_all(tmp_path)
    evaluate_barrier(tmp_path)
    with pytest.raises(SdkRuntimeError) as exc:
        promote_exact_pin_evidence(
            tmp_path, live_head=HEAD, live_tree=TREE, live_main=OTHER
        )
    assert exc.value.code == "SPECULATIVE_CERT_TARGET_MOVED"
    assert load_barrier(tmp_path).exact_pin_evidence_promoted is False


def test_new_p0_fails_barrier(tmp_path: Path) -> None:
    seal_candidate(tmp_path, generation=4, head=HEAD, tree=TREE, base_main=MAIN)
    for lane in REQUIRED_LANES:
        record_lane_result(
            tmp_path,
            LaneReceipt(
                lane=lane,
                result=LaneResult.PASS,
                head=HEAD,
                tree=TREE,
                new_p0=1 if lane == "ADV" else 0,
            ),
        )
    barrier = evaluate_barrier(tmp_path)
    assert barrier.state == CertificationState.BARRIER_FAILED
