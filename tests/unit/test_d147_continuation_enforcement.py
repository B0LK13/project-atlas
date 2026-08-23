"""D-147 — continuation enforcement regression (child task != directive terminal)."""

from project_atlas.orchestration.autonomy.return_gate import (
    AutonomyReturnState,
    autonomous_work_exists,
    may_emit_final_return,
)


def test_integration_ready_forbids_return() -> None:
    state = AutonomyReturnState(integration_ready=1)
    assert autonomous_work_exists(state)
    assert may_emit_final_return(state) is False


def test_post_merge_seal_pending_forbids_return() -> None:
    state = AutonomyReturnState(post_merge_seal_pending=1)
    assert autonomous_work_exists(state)
    assert may_emit_final_return(state) is False


def test_ci_green_merge_executable_forbids_return() -> None:
    """Watcher completes CI green but merge not done — still autonomous work."""
    state = AutonomyReturnState(integration_ready=1, ready_nodes=0)
    assert may_emit_final_return(state) is False


def test_owner_frontier_only_when_exhausted() -> None:
    state = AutonomyReturnState(
        genuine_owner_frontier=True,
        integration_ready=0,
        post_merge_seal_pending=0,
    )
    assert may_emit_final_return(state) is True
