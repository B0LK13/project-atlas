"""AS-OPT-GATE-001 — full governed experiment path via the scoring broker."""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.unit.opt_gate_helpers import (
    PUBLIC_WEAKER,
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
    holdout_root,
)
from project_atlas.opt_gate import ATLAS_OPT_WAKE_GATE, run_governed_experiment
from project_atlas.schema import validate_record
from project_atlas.scoring_broker import ScoringBrokerSession, open_broker_session

pytestmark = pytest.mark.integration


def _holdout_meta() -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    for path in sorted((holdout_root(REPO_ROOT) / "cases").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta[str(payload["case_id"])] = {
            "query": str(payload.get("query", "")),
            "score_mode": str(payload.get("score_mode", "exact")),
        }
    return meta


@pytest.fixture(autouse=True)
def _clear_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EVAL_SCORING_CAPABILITY_ENV, raising=False)
    monkeypatch.delenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, raising=False)


@pytest.fixture
def broker(tmp_path: Path) -> Iterator[tuple[ScoringBrokerSession, dict[str, str], str]]:
    meta = _holdout_meta()
    answers = {cid: f"answer-{secrets.token_hex(16)}" for cid in meta}
    query_to_answer = {meta[cid]["query"]: answers[cid] for cid in meta}
    private_dir = tmp_path / "operator-private"
    private_dir.mkdir()
    map_path = private_dir / "eval_holdout_expected.json"
    map_path.write_text(json.dumps(answers), encoding="utf-8")
    session = open_broker_session(
        repo_root=REPO_ROOT, expected_map_path=map_path, attempt_budget=8
    )
    try:
        yield session, query_to_answer, answers[next(iter(answers))]
    finally:
        session.close()


def _holdout_preds(
    session: ScoringBrokerSession, query_to_answer: dict[str, str]
) -> dict[str, str]:
    return {case.opaque_case_id: query_to_answer[case.query] for case in session.manifest()}


def test_promote_eligible_happy_path_does_not_wake_opt(
    broker: tuple[ScoringBrokerSession, dict[str, str], str],
    tmp_path: Path,
) -> None:
    session, query_to_answer, secret = broker
    holdout = _holdout_preds(session, query_to_answer)
    receipt = run_governed_experiment(
        repo_root=REPO_ROOT,
        experiment_id="exp-happy",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        baseline_config=baseline_config(),
        candidate_config=candidate_config(),
        baseline_arm=honest_arm(public=PUBLIC_WEAKER, holdout=holdout),
        candidate_arm=honest_arm(holdout=holdout),
        broker_session=session,
        seed=7,
        vault=tmp_path / "vault",
    )
    validate_record(receipt, "opt-experiment-receipt")
    assert receipt["promotion_decision"] == "PROMOTE_ELIGIBLE"
    assert receipt["decision_reason"] == "all-conditions-met"
    assert receipt["quality_score_considered"] is True
    assert receipt["opt_woken"] is False
    assert receipt["atlas_opt_wake_gate"] == ATLAS_OPT_WAKE_GATE == "CLOSED"
    assert receipt["authority_promoted"] is False
    dumped = json.dumps(receipt, sort_keys=True)
    assert secret not in dumped
    assert "EV-HOLD-101" not in dumped
    assert "EV-HOLD-102" not in dumped
    assert os.environ.get(EVAL_SCORING_CAPABILITY_ENV, "") != "1"


def test_always_answer_full_path_rejects_despite_perfect_holdout(
    broker: tuple[ScoringBrokerSession, dict[str, str], str],
) -> None:
    session, query_to_answer, secret = broker
    holdout = _holdout_preds(session, query_to_answer)
    answers = replace_answer(
        honest_answers(),
        "EV-GATE-UNK-001",
        status="known",
        predicted="always-an-answer",
        citations=("ev-alpha-status",),
        evidence_ids=("ev-alpha-status",),
    )
    receipt = run_governed_experiment(
        repo_root=REPO_ROOT,
        experiment_id="exp-always-answer",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        baseline_config=baseline_config(),
        candidate_config=candidate_config(),
        baseline_arm=honest_arm(holdout=holdout),
        candidate_arm=honest_arm(
            holdout=holdout, answers=answers, claimed_quality_score=1.0
        ),
        broker_session=session,
        seed=7,
    )
    assert receipt["promotion_decision"] == "REJECT"
    assert receipt["decision_reason"] == "hard-gate-failed"
    assert receipt["quality_score_considered"] is False
    assert receipt["hard_gate_outcomes"]["unknown_honesty"] == "FAIL"
    assert secret not in json.dumps(receipt)


def test_holdout_regression_full_path_rejects(
    broker: tuple[ScoringBrokerSession, dict[str, str], str],
) -> None:
    session, query_to_answer, _secret = broker
    correct = _holdout_preds(session, query_to_answer)
    wrong = {key: "wrong" for key in correct}
    receipt = run_governed_experiment(
        repo_root=REPO_ROOT,
        experiment_id="exp-holdout-reg",
        repo_head=REPO_HEAD,
        repo_tree=REPO_TREE,
        baseline_config=baseline_config(),
        candidate_config=candidate_config(),
        baseline_arm=honest_arm(holdout=correct),
        candidate_arm=honest_arm(holdout=wrong),
        broker_session=session,
        seed=7,
    )
    assert receipt["promotion_decision"] == "REJECT"
    assert receipt["decision_reason"] == "holdout-regressed"
    assert receipt["quality_score_considered"] is True
    assert receipt["hard_gate_outcomes"]["unknown_honesty"] == "PASS"


def test_experiment_determinism_semantic_receipt(
    tmp_path: Path,
) -> None:
    """Same sealed inputs → same semantic receipt (two broker sessions)."""
    meta = _holdout_meta()
    answers = {cid: f"det-{cid.lower()}" for cid in meta}
    query_to_answer = {info["query"]: answers[cid] for cid, info in meta.items()}
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(answers), encoding="utf-8")

    receipts: list[dict[str, object]] = []
    for _ in range(2):
        session = open_broker_session(
            repo_root=REPO_ROOT, expected_map_path=map_path, attempt_budget=8
        )
        try:
            holdout = _holdout_preds(session, query_to_answer)
            receipts.append(
                run_governed_experiment(
                    repo_root=REPO_ROOT,
                    experiment_id="exp-det",
                    repo_head=REPO_HEAD,
                    repo_tree=REPO_TREE,
                    baseline_config=baseline_config(),
                    candidate_config=candidate_config(),
                    baseline_arm=honest_arm(public=PUBLIC_WEAKER, holdout=holdout),
                    candidate_arm=honest_arm(holdout=holdout),
                    broker_session=session,
                    seed=7,
                )
            )
        finally:
            session.close()

    first, second = receipts
    assert first == second
    assert first["promotion_decision"] == "PROMOTE_ELIGIBLE"
    assert first["run_identity"] == second["run_identity"]
    assert first["receipt_digest"] == second["receipt_digest"]
