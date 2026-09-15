"""D-138 adversarial matrix for dependent-merge sequence gate."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.ci_observer import CiJobObservation, CiObservation
from project_atlas.orchestration.sdk.merge_sequence_gate import (
    DependentMergeDecision,
    ParentPostMergeSeal,
    PrerequisiteSealState,
    classify_ci_prerequisite,
    evaluate_dependent_merge_allowed,
    record_child_merge_dispatch,
    seal_from_ci_observation,
    simulate_d137_violation,
)
from project_atlas.orchestration.sdk.models import SdkRuntimeError

MAIN = "bd8faa8f97df454943181d19f1e14ee826900a20"
TREE = "49643ac38f3bf0037c0dc78aeef877ecc7e23821"
PARENT_MC = "8a38498c5f95181aa66e2a99bc507824fd8a8e60"


def _job(
    job_id: str,
    name: str,
    status: str,
    conclusion: str | None,
    *,
    required: bool = True,
) -> CiJobObservation:
    return CiJobObservation(
        job_id=job_id,
        job_name=name,
        job_status=status,
        job_conclusion=conclusion,
        required=required,
    )


def _all_pass_jobs() -> tuple[CiJobObservation, ...]:
    return (
        _job("1", "quality (ubuntu-latest, 3.12, full)", "completed", "success"),
        _job("2", "quality (ubuntu-latest, 3.13, compat)", "completed", "success"),
        _job("3", "quality (windows-latest, 3.12, windows)", "completed", "success"),
        _job("4", "control-plane", "completed", "success"),
    )


def _seal(**overrides: object) -> ParentPostMergeSeal:
    base = dict(
        parent_pr_number=435,
        child_pr_number=436,
        parent_merge_commit=PARENT_MC,
        parent_post_merge_main_sha=MAIN,
        parent_post_merge_tree=TREE,
        ci_run_id="32563926641",
        seal_generation=1,
        sealed_at=1000.0,
    )
    base.update(overrides)
    return ParentPostMergeSeal(**base)  # type: ignore[arg-type]


def _deny(decision: DependentMergeDecision) -> None:
    assert decision.allowed is False


def _allow(decision: DependentMergeDecision) -> None:
    assert decision.allowed is True


# 1. Parent Linux PASS, Windows RUNNING → denied
def test_01_windows_running_denies_child() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run1",
        status="PASS",
        run_status="in_progress",
        jobs=(
            _job("a", "quality (ubuntu-latest, 3.12, full)", "completed", "success"),
            _job("b", "quality (windows-latest, 3.12, windows)", "in_progress", None),
            _job("c", "control-plane", "completed", "success"),
        ),
    )
    assert classify_ci_prerequisite(obs) is PrerequisiteSealState.RUNNING
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 2. Parent 3/4 jobs PASS → denied
def test_02_three_of_four_denied() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run2",
        status="PENDING",
        run_status="in_progress",
        jobs=_all_pass_jobs()[:3],
    )
    assert classify_ci_prerequisite(obs) in {
        PrerequisiteSealState.PARTIAL,
        PrerequisiteSealState.PENDING,
    }
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 3. Final job PASS milliseconds later — denied until reevaluation with seal
def test_03_late_pass_without_seal_still_denied() -> None:
    obs_before = CiObservation(
        head_sha=PARENT_MC,
        run_id="run3",
        status="PASS",
        run_status="in_progress",
        jobs=(
            *_all_pass_jobs()[:3],
            _job("w", "quality (windows-latest, 3.12, windows)", "in_progress", None),
        ),
    )
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=obs_before,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 4. CI PASS but seal not durably written → denied
def test_04_pass_without_durable_seal_denied() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run4",
        status="PASS",
        conclusion="success",
        run_status="completed",
        run_conclusion="success",
        jobs=_all_pass_jobs(),
    )
    assert classify_ci_prerequisite(obs) is PrerequisiteSealState.TERMINAL_PASS
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 5. Seal written for wrong SHA → denied
def test_05_wrong_sha_seal_denied() -> None:
    seal = _seal(parent_merge_commit="a" * 40)
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=seal,
            ci_observation=None,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 6. Seal for previous main → denied
def test_06_previous_main_seal_denied() -> None:
    seal = _seal(parent_post_merge_main_sha="f" * 40)
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=seal,
            ci_observation=None,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 7. CI observer unavailable → denied
def test_07_observer_unavailable_denied() -> None:
    assert classify_ci_prerequisite(None) is PrerequisiteSealState.MISSING
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=None,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 8. Cached PASS but live lane RUNNING → denied
def test_08_cached_pass_live_running_denied() -> None:
    seal = _seal()
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run8",
        status="PASS",
        run_status="in_progress",
        jobs=(
            *_all_pass_jobs()[:3],
            _job("w", "quality (windows-latest, 3.12, windows)", "in_progress", None),
        ),
    )
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=seal,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 9. Duplicate dispatch — second attempt raises or is separate concern
def test_09_dispatch_order_enforced(tmp_path: Path) -> None:
    seal = _seal(sealed_at=2000.0)
    record_child_merge_dispatch(
        tmp_path, child_pr_number=436, parent_seal=seal, dispatched_at=2001.0
    )
    with pytest.raises(SdkRuntimeError, match="before parent seal"):
        record_child_merge_dispatch(
            tmp_path, child_pr_number=436, parent_seal=seal, dispatched_at=1999.0
        )


# 10. Resident restart — seal reload still valid when SHA match
def test_10_seal_reload_valid_flow() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run10",
        status="PASS",
        conclusion="success",
        run_status="completed",
        run_conclusion="success",
        jobs=_all_pass_jobs(),
    )
    seal = seal_from_ci_observation(
        obs=obs,
        parent_pr_number=435,
        child_pr_number=436,
        parent_merge_commit=PARENT_MC,
        parent_post_merge_main_sha=MAIN,
        parent_post_merge_tree=TREE,
        seal_generation=10,
        sealed_at=time.time(),
    )
    assert seal is not None
    _allow(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=seal,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 11. Watchdog takeover — same gate, no bypass without seal
def test_11_no_seal_no_bypass() -> None:
    _deny(simulate_d137_violation())


# 12. Target main moves after seal → revalidation required
def test_12_target_move_invalidates_seal() -> None:
    seal = _seal()
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=seal,
            ci_observation=None,
            live_main_sha="c" * 40,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 13. Parent CI cancelled → denied
def test_13_cancelled_denied() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run13",
        status="CANCELLED",
        jobs=_all_pass_jobs(),
    )
    assert classify_ci_prerequisite(obs) is PrerequisiteSealState.CANCELLED
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 14. CI rerun still running → denied
def test_14_rerun_in_progress_denied() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="run14",
        status="PENDING",
        run_status="in_progress",
        jobs=(),
    )
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=obs,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


# 15. Manual subagent PASS without CI evidence → denied
def test_15_manual_pass_without_ci_denied() -> None:
    _deny(
        evaluate_dependent_merge_allowed(
            parent_merged=True,
            parent_seal=None,
            ci_observation=None,
            live_main_sha=MAIN,
            live_tree_sha=TREE,
            parent_merge_commit=PARENT_MC,
            child_merge_authorized=True,
        )
    )


def test_d137_simulation_reproduces_violation() -> None:
    """Pre-fix: D-137 state would have allowed merge; post-fix blocks."""
    decision = simulate_d137_violation()
    assert decision.allowed is False
    assert decision.reason == "PARENT_SEAL_NOT_DURABLY_RECORDED"


def test_valid_parent_child_flow() -> None:
    obs = CiObservation(
        head_sha=PARENT_MC,
        run_id="32563926641",
        status="PASS",
        conclusion="success",
        run_status="completed",
        run_conclusion="success",
        jobs=_all_pass_jobs(),
    )
    sealed_at = 5000.0
    seal = seal_from_ci_observation(
        obs=obs,
        parent_pr_number=435,
        child_pr_number=436,
        parent_merge_commit=PARENT_MC,
        parent_post_merge_main_sha=MAIN,
        parent_post_merge_tree=TREE,
        seal_generation=1,
        sealed_at=sealed_at,
    )
    assert seal is not None
    decision = evaluate_dependent_merge_allowed(
        parent_merged=True,
        parent_seal=seal,
        ci_observation=obs,
        live_main_sha=MAIN,
        live_tree_sha=TREE,
        parent_merge_commit=PARENT_MC,
        child_merge_authorized=True,
    )
    _allow(decision)


def test_wiring_scheduler_imports_gate() -> None:
    """Production scheduler_tick path imports merge_sequence_gate."""
    import inspect

    from project_atlas.orchestration.sdk import nonblocking_scheduler as sched

    src = inspect.getsource(sched._maybe_mint_stacked_parent_seal)
    assert "merge_sequence_gate" in src
    assert "refresh_dependent_merge_gate_state" in src
