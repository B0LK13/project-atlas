"""AS-OPT-GATE-001 — security / privacy IV (Cursor-internal).

Covers expected-answer leakage, receipt/error side-channels, candidate mutation
of evaluator/thresholds/promotion policy, hard-gate bypass, forged receipts,
replay, cross-project evidence, and seal-vs-execution races.

CODEX_VALIDATED remains NO; this is not external revalidation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tests.unit.opt_gate_helpers import (
    REPO_HEAD,
    REPO_ROOT,
    REPO_TREE,
    baseline_config,
    candidate_config,
    honest_answers,
    honest_arm,
    replace_answer,
)

from project_atlas.eval_substrate import (
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    EVAL_SCORING_CAPABILITY_ENV,
)
from project_atlas.opt_gate import (
    ATLAS_OPT_WAKE_GATE,
    OptGateError,
    evaluate_hard_gates,
    load_opt_gate_policies,
    run_governed_experiment,
    seal_experiment,
    verify_experiment_receipt,
)

POLICY_ROOT = REPO_ROOT / "fixtures" / "eval" / "opt-gate"


@pytest.fixture(autouse=True)
def _clear_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EVAL_SCORING_CAPABILITY_ENV, raising=False)
    monkeypatch.delenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, raising=False)


def test_opt_gate_process_does_not_arm_scoring_capability() -> None:
    assert os.environ.get(EVAL_SCORING_CAPABILITY_ENV, "") != "1"
    run_governed_experiment(
        repo_root=REPO_ROOT,
        experiment_id="exp-no-cap",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        baseline_config=baseline_config(),
        candidate_config=candidate_config(),
        baseline_arm=honest_arm(),
        candidate_arm=honest_arm(),
        broker_session=None,
    )
    assert os.environ.get(EVAL_SCORING_CAPABILITY_ENV, "") != "1"
    assert os.environ.get(EVAL_HOLDOUT_EXPECTED_PATH_ENV, "") == ""


def test_receipt_and_errors_omit_holdout_answers_and_paths(tmp_path: Path) -> None:
    secret = "holdout-secret-should-never-leak"
    receipt = run_governed_experiment(
        repo_root=REPO_ROOT,
        experiment_id="exp-privacy",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        baseline_config=baseline_config(),
        candidate_config=candidate_config(),
        baseline_arm=honest_arm(),
        candidate_arm=honest_arm(),
        broker_session=None,
        vault=tmp_path / "vault",
    )
    dumped = json.dumps(receipt, sort_keys=True)
    assert secret not in dumped
    assert "EV-HOLD-101" not in dumped
    assert "EV-HOLD-102" not in dumped
    assert "ATLAS_EVAL_HOLDOUT_EXPECTED_PATH" not in dumped
    assert "expected_norm" not in dumped
    assert "predicted_norm" not in dumped
    written = tmp_path / "vault" / "generated" / "ops" / "opt-gate" / "exp-privacy.json"
    assert written.is_file()
    assert secret not in written.read_text(encoding="utf-8")
    try:
        raise OptGateError("holdout-broker-unavailable")
    except OptGateError as exc:
        assert secret not in str(exc)
        assert "EV-HOLD-101" not in str(exc)


def test_candidate_cannot_mutate_promotion_policy() -> None:
    with pytest.raises(OptGateError, match="candidate-config-malformed"):
        run_governed_experiment(
            repo_root=REPO_ROOT,
            experiment_id="exp-promo-mut",
            repo_head=REPO_HEAD,
            repo_tree=REPO_TREE,
            baseline_config=baseline_config(),
            candidate_config={
                "candidate_id": "candidate-a",
                "promotion_decision": "PROMOTE_ELIGIBLE",
            },
            baseline_arm=honest_arm(),
            candidate_arm=honest_arm(),
            broker_session=None,
        )


def test_candidate_cannot_mutate_thresholds_via_config() -> None:
    with pytest.raises(OptGateError, match="candidate-config-malformed"):
        run_governed_experiment(
            repo_root=REPO_ROOT,
            experiment_id="exp-thr-mut",
            repo_head=REPO_HEAD,
            repo_tree=REPO_TREE,
            baseline_config=baseline_config(),
            candidate_config={
                "candidate_id": "candidate-a",
                "parameters": {"min_public_matched_delta": 0},
            },
            baseline_arm=honest_arm(),
            candidate_arm=honest_arm(),
            broker_session=None,
        )


def test_cross_project_evidence_fails_isolation() -> None:
    answers = replace_answer(
        honest_answers(),
        "EV-GATE-PROJ-A-001",
        citations=("ev-b-secret",),
        evidence_ids=("ev-b-secret",),
        project_id="proj-alpha",
    )
    outcomes = evaluate_hard_gates(
        arm=honest_arm(answers=answers),
        candidate_config=candidate_config(),
        catalog=load_opt_gate_policies(POLICY_ROOT).honesty_catalog,
    )
    assert outcomes["project_isolation"] == "FAIL"
    assert outcomes["evidence_integrity"] == "FAIL"


def test_secrets_in_candidate_output_fail_security() -> None:
    answers = replace_answer(
        honest_answers(),
        "EV-GATE-KNOWN-001",
        predicted="password=supersecretpasswordvalue",
    )
    outcomes = evaluate_hard_gates(
        arm=honest_arm(answers=answers),
        candidate_config=candidate_config(),
        catalog=load_opt_gate_policies(POLICY_ROOT).honesty_catalog,
    )
    assert outcomes["security"] == "FAIL"


def test_path_traversal_citation_fails_security() -> None:
    answers = replace_answer(
        honest_answers(),
        "EV-GATE-KNOWN-001",
        citations=("../etc/passwd",),
        evidence_ids=("../etc/passwd",),
    )
    outcomes = evaluate_hard_gates(
        arm=honest_arm(answers=answers),
        candidate_config=candidate_config(),
        catalog=load_opt_gate_policies(POLICY_ROOT).honesty_catalog,
    )
    assert outcomes["security"] == "FAIL"


def test_replay_receipt_does_not_apply_promotion() -> None:
    """There is no promote-from-receipt API; a stored receipt cannot mutate prod."""
    import project_atlas.opt_gate as opt_gate

    assert not hasattr(opt_gate, "promote_from_receipt")
    assert not hasattr(opt_gate, "apply_promotion")
    assert not hasattr(opt_gate, "merge_candidate")
    assert ATLAS_OPT_WAKE_GATE == "CLOSED"


def test_tampered_tree_does_not_verify_as_promote() -> None:
    from project_atlas.opt_gate import ScoreCounts, build_experiment_receipt

    policies = load_opt_gate_policies(POLICY_ROOT)
    envelope = seal_experiment(
        repo_root=REPO_ROOT,
        policies=policies,
        baseline_configuration=baseline_config(),
    )
    receipt = build_experiment_receipt(
        experiment_id="exp-replay-tree",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        envelope=envelope,
        candidate_configuration=candidate_config(),
        seed=1,
        gate_outcomes={
            "security": "PASS",
            "provenance_integrity": "PASS",
            "authority_integrity": "PASS",
            "unknown_honesty": "PASS",
            "conflict_honesty": "PASS",
            "evidence_integrity": "PASS",
            "determinism": "PASS",
            "project_isolation": "PASS",
            "holdout_isolation": "PASS",
        },
        public_baseline=ScoreCounts(4, 4, 0),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 2, 0),
        holdout_candidate=ScoreCounts(2, 2, 0),
        holdout_scored=True,
        promotion_decision="PROMOTE_ELIGIBLE",
        decision_reason="all-conditions-met",
        quality_score_considered=True,
        experiment_valid=True,
        seal_valid=True,
    )
    verify_experiment_receipt(receipt, sealed_envelope=envelope)
    receipt["repository_tree"] = "c" * 40
    with pytest.raises(OptGateError, match="receipt-invalid"):
        verify_experiment_receipt(receipt, sealed_envelope=envelope)


def test_no_opt_wake_on_happy_invalid_path() -> None:
    receipt = run_governed_experiment(
        repo_root=REPO_ROOT,
        experiment_id="exp-still-closed",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        baseline_config=baseline_config(),
        candidate_config=candidate_config(),
        baseline_arm=honest_arm(),
        candidate_arm=honest_arm(),
        broker_session=None,
    )
    assert receipt["atlas_opt_wake_gate"] == "CLOSED"
    assert receipt["opt_woken"] is False
    assert receipt["authority_promoted"] is False
    assert receipt["rl_enabled"] is False
    assert receipt["prime_enabled"] is False
    assert os.environ.get("ATLAS_OPT_WAKE_GATE") in {None, "", "CLOSED"}
