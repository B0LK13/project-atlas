"""Monotonic observed task consumption across controller invocations."""

from __future__ import annotations

from project_atlas.orchestration.program.continuation import (
    ConsumedBudget,
    ContinuationCheckpoint,
)
from project_atlas.orchestration.program.store import ProgramStateRecord


def unobserved_wall_attempts(state: ProgramStateRecord, task_id: str) -> tuple[str, ...]:
    """Unknown historical measurements are not free time for a new dispatch."""
    return tuple(
        a.attempt_id
        for a in state.attempts.values()
        if a.task_id == task_id
        and a.phase.value != "INTENT_RECORDED"
        and a.duration_seconds is None
    )


def consumed_for_task(
    state: ProgramStateRecord, task_id: str, checkpoint: ContinuationCheckpoint | None
) -> ConsumedBudget:
    prior = checkpoint.consumed_budget if checkpoint else ConsumedBudget()
    record = state.tasks[task_id]
    attempts = [a for a in state.attempts.values() if a.task_id == task_id]
    return prior.model_copy(
        update={
            "attempts": max(prior.attempts, record.attempts),
            "launches": max(prior.launches, record.launches),
            "wall_seconds": max(
                prior.wall_seconds, sum(a.duration_seconds or 0.0 for a in attempts)
            ),
            "estimated_cost_usd": max(
                prior.estimated_cost_usd, sum(a.estimated_cost_usd or 0.0 for a in attempts)
            ),
        }
    )
