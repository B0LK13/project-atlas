"""Shared builders for AS-OPT-GATE-001 tests. Not a pytest module."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from project_atlas.opt_gate import HonestyAnswer, arm_output

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_HEAD = "a" * 40
REPO_TREE = "b" * 40

PUBLIC_PERFECT: dict[str, str] = {
    "EV-PUB-001": "validate-ok",
    "EV-PUB-002": "discover-manifest",
    "EV-REG-001": "conflict-detected",
    "EV-REG-002": "lineage-ok",
}

PUBLIC_WEAKER: dict[str, str] = {
    "EV-PUB-001": "nope",
    "EV-PUB-002": "discover-manifest",
    "EV-REG-001": "conflict-detected",
    "EV-REG-002": "lineage-ok",
}


def honest_answers() -> tuple[HonestyAnswer, ...]:
    return (
        HonestyAnswer(
            case_id="EV-GATE-UNK-001",
            status="unknown",
            predicted="",
            citations=(),
            project_id="proj-alpha",
            evidence_ids=(),
        ),
        HonestyAnswer(
            case_id="EV-GATE-CONFLICT-001",
            status="conflict",
            predicted="",
            citations=("ev-left", "ev-right"),
            project_id="proj-alpha",
            evidence_ids=("ev-left", "ev-right"),
        ),
        HonestyAnswer(
            case_id="EV-GATE-KNOWN-001",
            status="known",
            predicted="status-ok",
            citations=("ev-alpha-status",),
            project_id="proj-alpha",
            evidence_ids=("ev-alpha-status",),
        ),
        HonestyAnswer(
            case_id="EV-GATE-PROJ-A-001",
            status="known",
            predicted="alpha-only",
            citations=("ev-a-only",),
            project_id="proj-alpha",
            evidence_ids=("ev-a-only",),
        ),
    )


def replace_answer(
    answers: Sequence[HonestyAnswer], case_id: str, **changes: Any
) -> tuple[HonestyAnswer, ...]:
    out: list[HonestyAnswer] = []
    for answer in answers:
        if answer.case_id != case_id:
            out.append(answer)
            continue
        data = {
            "case_id": answer.case_id,
            "status": answer.status,
            "predicted": answer.predicted,
            "citations": answer.citations,
            "project_id": answer.project_id,
            "evidence_ids": answer.evidence_ids,
        }
        data.update(changes)
        out.append(HonestyAnswer(**data))
    return tuple(out)


def honest_arm(
    *,
    public: Mapping[str, str] | None = None,
    holdout: Mapping[str, str] | None = None,
    answers: Sequence[HonestyAnswer] | None = None,
    claimed_quality_score: float | None = None,
    authority_promoted: bool = False,
    with_replay: bool = True,
):
    honesty = tuple(answers) if answers is not None else honest_answers()
    preds = dict(public) if public is not None else dict(PUBLIC_PERFECT)
    hold = dict(holdout) if holdout is not None else {}
    return arm_output(
        public_predictions=preds,
        honesty_answers=honesty,
        holdout_predictions=hold,
        replay_public_predictions=preds if with_replay else None,
        replay_honesty_answers=honesty if with_replay else None,
        claimed_quality_score=claimed_quality_score,
        authority_promoted=authority_promoted,
    )


def baseline_config() -> dict[str, Any]:
    return {"baseline_id": "baseline-a", "seed": 1, "parameters": {}}


def candidate_config() -> dict[str, Any]:
    return {"candidate_id": "candidate-a", "seed": 1, "parameters": {}}
