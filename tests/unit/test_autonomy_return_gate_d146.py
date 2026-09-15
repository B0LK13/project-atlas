"""D-146 — autonomy return gate adversarial cases."""

from project_atlas.orchestration.autonomy.return_gate import (
    AutonomyReturnState,
    autonomous_work_exists,
    final_response_precheck,
    may_emit_final_return,
)


def _state(**kwargs: object) -> AutonomyReturnState:
    return AutonomyReturnState.model_validate(kwargs)


def test_case1_ready_denies_return() -> None:
    state = _state(ready_nodes=1)
    assert autonomous_work_exists(state)
    assert may_emit_final_return(state) is False
    assert final_response_precheck(state)["suppress_final_response"] is True


def test_case2_uncertified_denies_return() -> None:
    state = _state(uncertified_changes=6)
    assert may_emit_final_return(state) is False


def test_case3_derivable_successor_denies_return() -> None:
    state = _state(derivable_successors=1)
    assert may_emit_final_return(state) is False


def test_case4_recoverable_failure_denies_return() -> None:
    state = _state(recoverable_failed_nodes=1)
    assert may_emit_final_return(state) is False


def test_case5_owner_blocked_plus_ready_denies_return() -> None:
    state = _state(ready_nodes=1, preparable_blocked_work=0)
    assert may_emit_final_return(state) is False


def test_case6_preparable_blocked_denies_return() -> None:
    state = _state(preparable_blocked_work=3)
    assert may_emit_final_return(state) is False


def test_case7_owner_frontier_allows_return_when_exhausted() -> None:
    state = _state(genuine_owner_frontier=True, closure_integrity_pass=True)
    assert may_emit_final_return(state) is True


def test_owner_frontier_without_closure_integrity_denies_return() -> None:
    state = _state(genuine_owner_frontier=True, closure_integrity_pass=False)
    assert may_emit_final_return(state) is False
    assert final_response_precheck(state)["suppress_final_response"] is True


def test_external_hard_blocker_allows_return_without_closure() -> None:
    state = _state(external_hard_blocker=True, closure_integrity_pass=False)
    assert may_emit_final_return(state) is True


def test_case8_terminal_allows_return() -> None:
    state = _state(project_terminal=True)
    assert may_emit_final_return(state) is True


def test_no_work_without_frontier_denies_return() -> None:
    state = _state()
    assert may_emit_final_return(state) is False
