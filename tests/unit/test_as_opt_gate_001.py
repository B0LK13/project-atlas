"""AS-OPT-GATE-001 — hard-gate contract, promotion order, determinism, receipts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.unit.opt_gate_helpers import (
    PUBLIC_PERFECT,
    REPO_ROOT,
    honest_answers,
    honest_arm,
    replace_answer,
)

from project_atlas.opt_gate import (
    ATLAS_OPT_WAKE_GATE,
    PACKAGE_ID,
    REQUIRED_HARD_GATES,
    HonestyAnswer,
    OptGateError,
    ScoreCounts,
    decide_promotion,
    evaluate_hard_gates,
    load_opt_gate_policies,
    seal_experiment,
    verify_experiment_receipt,
    verify_sealed_envelope,
)
from project_atlas.schema import available_schemas, validate_record

POLICY_ROOT = REPO_ROOT / "fixtures" / "eval" / "opt-gate"


def _catalog() -> dict:
    return load_opt_gate_policies(POLICY_ROOT).honesty_catalog


def test_schema_registered() -> None:
    assert "opt-experiment-receipt" in available_schemas()
    assert PACKAGE_ID == "AS-OPT-GATE-001"


def test_wake_gate_remains_closed() -> None:
    from project_atlas import opt_gate as opt_gate_mod

    assert ATLAS_OPT_WAKE_GATE == "CLOSED"
    source = Path(opt_gate_mod.__file__).read_text(encoding="utf-8")
    assert 'ATLAS_OPT_WAKE_GATE: Final[str] = "CLOSED"' in source
    assert "OPEN_ELIGIBLE" not in source


def test_honest_arm_passes_all_hard_gates() -> None:
    outcomes = evaluate_hard_gates(
        arm=honest_arm(),
        candidate_config={"candidate_id": "candidate-a", "seed": 1, "parameters": {}},
        catalog=_catalog(),
    )
    assert set(outcomes) == set(REQUIRED_HARD_GATES)
    assert all(outcomes[name] == "PASS" for name in REQUIRED_HARD_GATES)
    assert "UNKNOWN" not in outcomes.values()


def test_unknown_gate_name_fail_closed() -> None:
    with pytest.raises(OptGateError, match="gate-unknown"):
        evaluate_hard_gates(
            arm=honest_arm(),
            candidate_config={"candidate_id": "candidate-a", "seed": 1, "parameters": {}},
            catalog=_catalog(),
            required_gates=("security", "not-a-gate"),
        )


def test_missing_gate_fail_closed() -> None:
    with pytest.raises(OptGateError, match="gate-missing"):
        evaluate_hard_gates(
            arm=honest_arm(),
            candidate_config={"candidate_id": "candidate-a", "seed": 1, "parameters": {}},
            catalog=_catalog(),
            required_gates=REQUIRED_HARD_GATES[:-1],
        )


def test_hard_gates_precede_score_perfect_quality_still_reject() -> None:
    """ANY_HARD_GATE_FAIL → REJECT even if quality_score is perfect (G)."""
    failed = {name: "FAIL" for name in REQUIRED_HARD_GATES}
    failed["security"] = "FAIL"
    for name in REQUIRED_HARD_GATES:
        if name != "security":
            failed[name] = "PASS"
    decision, reason, considered = decide_promotion(
        experiment_valid=True,
        seal_valid=True,
        receipt_schema_valid=True,
        gate_outcomes=failed,
        public_baseline=ScoreCounts(4, 3, 1),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 2, 0),
        holdout_candidate=ScoreCounts(2, 2, 0),
        thresholds={
            "min_public_matched_delta": 0,
            "min_public_rate_improvement_millis": 0,
        },
    )
    assert decision == "REJECT"
    assert reason == "hard-gate-failed"
    assert considered is False


def test_quality_not_consulted_when_any_gate_unknown_coerced_to_fail() -> None:
    """A non-PASS result cannot count as PASS; quality stays unconsidered."""
    outcomes = {name: "PASS" for name in REQUIRED_HARD_GATES}
    outcomes["unknown_honesty"] = "UNKNOWN"  # type: ignore[assignment]
    decision, reason, considered = decide_promotion(
        experiment_valid=True,
        seal_valid=True,
        receipt_schema_valid=True,
        gate_outcomes=outcomes,
        public_baseline=ScoreCounts(4, 0, 4),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 1, 1),
        holdout_candidate=ScoreCounts(2, 2, 0),
        thresholds={
            "min_public_matched_delta": 0,
            "min_public_rate_improvement_millis": 0,
        },
    )
    assert decision == "INVALID_EXPERIMENT"
    assert reason == "gate-unknown"
    assert considered is False


def test_promote_eligible_only_when_all_conditions_met() -> None:
    outcomes = {name: "PASS" for name in REQUIRED_HARD_GATES}
    decision, reason, considered = decide_promotion(
        experiment_valid=True,
        seal_valid=True,
        receipt_schema_valid=True,
        gate_outcomes=outcomes,
        public_baseline=ScoreCounts(4, 3, 1),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 1, 1),
        holdout_candidate=ScoreCounts(2, 2, 0),
        thresholds={
            "min_public_matched_delta": 0,
            "min_public_rate_improvement_millis": 0,
        },
    )
    assert decision == "PROMOTE_ELIGIBLE"
    assert reason == "all-conditions-met"
    assert considered is True


def test_holdout_regression_rejects_after_gates_pass() -> None:
    outcomes = {name: "PASS" for name in REQUIRED_HARD_GATES}
    decision, reason, considered = decide_promotion(
        experiment_valid=True,
        seal_valid=True,
        receipt_schema_valid=True,
        gate_outcomes=outcomes,
        public_baseline=ScoreCounts(4, 3, 1),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 2, 0),
        holdout_candidate=ScoreCounts(2, 1, 1),
        thresholds={
            "min_public_matched_delta": 0,
            "min_public_rate_improvement_millis": 0,
        },
    )
    assert decision == "REJECT"
    assert reason == "holdout-regressed"
    assert considered is True


def test_quality_threshold_rejects_after_gates_pass() -> None:
    outcomes = {name: "PASS" for name in REQUIRED_HARD_GATES}
    decision, reason, considered = decide_promotion(
        experiment_valid=True,
        seal_valid=True,
        receipt_schema_valid=True,
        gate_outcomes=outcomes,
        public_baseline=ScoreCounts(4, 4, 0),
        public_candidate=ScoreCounts(4, 3, 1),
        holdout_baseline=ScoreCounts(2, 2, 0),
        holdout_candidate=ScoreCounts(2, 2, 0),
        thresholds={
            "min_public_matched_delta": 1,
            "min_public_rate_improvement_millis": 0,
        },
    )
    assert decision == "REJECT"
    assert reason == "quality-threshold-not-met"
    assert considered is True


def test_seal_roundtrip_stable() -> None:
    policies = load_opt_gate_policies(POLICY_ROOT)
    envelope = seal_experiment(
        repo_root=REPO_ROOT,
        policies=policies,
        baseline_configuration={"baseline_id": "baseline-a", "seed": 1, "parameters": {}},
    )
    assert verify_sealed_envelope(envelope) is True
    again = seal_experiment(
        repo_root=REPO_ROOT,
        policies=policies,
        baseline_configuration={"baseline_id": "baseline-a", "seed": 1, "parameters": {}},
    )
    assert again.envelope_digest == envelope.envelope_digest
    assert again.component_digests == envelope.component_digests


def test_evaluate_hard_gates_deterministic() -> None:
    catalog = _catalog()
    config = {"candidate_id": "candidate-a", "seed": 1, "parameters": {}}
    first = evaluate_hard_gates(arm=honest_arm(), candidate_config=config, catalog=catalog)
    second = evaluate_hard_gates(arm=honest_arm(), candidate_config=config, catalog=catalog)
    assert first == second


def test_candidate_supplied_gate_outcomes_are_not_an_input() -> None:
    """Gate outcomes are computed; stuffing PASS into config cannot help."""
    config = {
        "candidate_id": "candidate-a",
        "seed": 1,
        "parameters": {},
    }
    answers = replace_answer(
        honest_answers(),
        "EV-GATE-UNK-001",
        status="known",
        predicted="invented-confident-answer",
    )
    outcomes = evaluate_hard_gates(
        arm=honest_arm(answers=answers),
        candidate_config=config,
        catalog=_catalog(),
    )
    assert outcomes["unknown_honesty"] == "FAIL"


def test_receipt_schema_and_digest_roundtrip() -> None:
    from project_atlas.opt_gate import build_experiment_receipt

    policies = load_opt_gate_policies(POLICY_ROOT)
    envelope = seal_experiment(
        repo_root=REPO_ROOT,
        policies=policies,
        baseline_configuration={"baseline_id": "baseline-a", "seed": 1, "parameters": {}},
    )
    outcomes = {name: "PASS" for name in REQUIRED_HARD_GATES}
    receipt = build_experiment_receipt(
        experiment_id="exp-receipt-a",
        repo_head="a" * 40,
        repo_tree="b" * 40,
        envelope=envelope,
        candidate_configuration={"candidate_id": "candidate-a", "seed": 1, "parameters": {}},
        seed=1,
        gate_outcomes=outcomes,
        public_baseline=ScoreCounts(4, 3, 1),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 1, 1),
        holdout_candidate=ScoreCounts(2, 2, 0),
        holdout_scored=True,
        promotion_decision="PROMOTE_ELIGIBLE",
        decision_reason="all-conditions-met",
        quality_score_considered=True,
        experiment_valid=True,
        seal_valid=True,
    )
    validate_record(receipt, "opt-experiment-receipt")
    verify_experiment_receipt(receipt, sealed_envelope=envelope)
    text = json.dumps(receipt, sort_keys=True)
    assert "expected" not in receipt["holdout_aggregate"]
    assert "EV-HOLD-101" not in text
    assert "EV-HOLD-102" not in text
    assert receipt["opt_woken"] is False
    assert receipt["atlas_opt_wake_gate"] == "CLOSED"
    assert receipt["scoring_authority"] == "engine"
    assert "generated.at" not in text


def test_forged_promote_decision_rejected() -> None:
    from project_atlas.opt_gate import _receipt_digest_for, build_experiment_receipt

    policies = load_opt_gate_policies(POLICY_ROOT)
    envelope = seal_experiment(
        repo_root=REPO_ROOT,
        policies=policies,
        baseline_configuration={"baseline_id": "baseline-a", "seed": 1, "parameters": {}},
    )
    outcomes = {name: "PASS" for name in REQUIRED_HARD_GATES}
    outcomes["evidence_integrity"] = "FAIL"
    receipt = build_experiment_receipt(
        experiment_id="exp-forged",
        repo_head="a" * 40,
        repo_tree="b" * 40,
        envelope=envelope,
        candidate_configuration={"candidate_id": "candidate-a", "seed": 1, "parameters": {}},
        seed=1,
        gate_outcomes=outcomes,
        public_baseline=ScoreCounts(4, 4, 0),
        public_candidate=ScoreCounts(4, 4, 0),
        holdout_baseline=ScoreCounts(2, 2, 0),
        holdout_candidate=ScoreCounts(2, 2, 0),
        holdout_scored=True,
        promotion_decision="REJECT",
        decision_reason="hard-gate-failed",
        quality_score_considered=False,
        experiment_valid=True,
        seal_valid=True,
    )
    receipt["promotion_decision"] = "PROMOTE_ELIGIBLE"
    receipt["receipt_digest"] = _receipt_digest_for(receipt)
    with pytest.raises(OptGateError, match="receipt-invalid"):
        verify_experiment_receipt(receipt, sealed_envelope=envelope)
    with pytest.raises(OptGateError, match="receipt-invalid"):
        verify_experiment_receipt(receipt)


def test_public_predictions_do_not_include_holdout_ids() -> None:
    arm = honest_arm(public={**PUBLIC_PERFECT, "EV-HOLD-101": "guess"})
    outcomes = evaluate_hard_gates(
        arm=arm,
        candidate_config={"candidate_id": "candidate-a", "seed": 1, "parameters": {}},
        catalog=_catalog(),
    )
    assert outcomes["holdout_isolation"] == "FAIL"


def test_honesty_answers_are_frozen_tuples() -> None:
    first = honest_answers()
    second = honest_answers()
    assert first == second
    assert isinstance(first[0], HonestyAnswer)
