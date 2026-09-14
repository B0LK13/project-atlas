"""Controller-owned, one-dispatch-per-step continuation (zero-model fixture).

Worker output never grants authority or seals completion. The parent records
intent before spawn and seals a step only after observed exit and acceptance.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.orchestration.program.adapters.base import pid_is_alive
from project_atlas.orchestration.program.consumption import (
    consumed_for_task,
    unobserved_wall_attempts,
)
from project_atlas.orchestration.program.continuation import (
    ConsumedBudget,
    ContinuationCheckpoint,
    ExecutionCapture,
    ExecutionCaptureReport,
    ExecutionIdentity,
    ReplayClass,
    load_checkpoint,
    load_envelope,
    persist_checkpoint,
    utc_now,
)
from project_atlas.orchestration.program.continuation_projection import (
    _CHANGED_FILES_UNAVAILABLE,
    _capture_artifacts,
    _capture_commands,
    _lease_snapshot,
)
from project_atlas.orchestration.program.models import (
    ExecutionConfidence,
    ExecutionStep,
    ProgramError,
    ProgramTask,
)
from project_atlas.orchestration.program.reconciliation import holder_liveness
from project_atlas.orchestration.program.recovery import Liveness
from project_atlas.orchestration.program.store import AttemptRecord, ProgramStateRecord, load_state


def selected_step(root: Path, task: ProgramTask) -> ExecutionStep:
    envelope = load_envelope(root, task.task_id)
    if envelope is None or envelope.replay_class is not ReplayClass.CHECKPOINT_RESUMABLE:
        raise ProgramError(
            "step execution requires a checkpoint-resumable envelope", code="STEP_ENVELOPE_REQUIRED"
        )
    if envelope.checkpoint_policy.steps != tuple(s.step_id for s in task.execution_steps):
        raise ProgramError("approved task and envelope steps differ", code="STEP_PLAN_MISMATCH")
    cp = load_checkpoint(root, task.task_id)
    next_id = envelope.next_step_after(cp.last_completed_step if cp else None)
    for step in task.execution_steps:
        if step.step_id == next_id:
            return step
    raise ProgramError(
        "all steps complete without final task seal", code="STEP_FINAL_SEAL_REQUIRED"
    )


def completed_boundary(root: Path, task: ProgramTask, state: ProgramStateRecord) -> bool:
    """A sealed observed receipt must also match the actual durable attempt."""
    cp = load_checkpoint(root, task.task_id)
    if cp is None:
        return True
    attempt = state.attempts.get(cp.identity.attempt_id)
    steps = tuple(s.step_id for s in task.execution_steps)
    if cp.last_completed_step not in steps:
        return False
    prefix = task.execution_steps[: steps.index(cp.last_completed_step) + 1]
    if len(cp.commands) != len(prefix) or any(
        command.argv != step.argv or command.exit_status != 0
        for command, step in zip(cp.commands, prefix, strict=True)
    ):
        return False
    # IV-STEP-05: the final receipt is not authority for an earlier step.
    # Require one durable accepted attempt and its observed transcript for
    # every approved prefix command. Missing, duplicate or contradictory
    # receipts require reconciliation, never reconstructed success.
    for command, step in zip(cp.commands, prefix, strict=True):
        receipts = [
            item for item in state.attempts.values()
            if item.task_id == task.task_id and item.step_id == step.step_id
        ]
        if len(receipts) != 1:
            return False
        receipt = receipts[0]
        if (
            receipt.exit_status != 0
            or receipt.confidence is not ExecutionConfidence.CONFIRMED
            or receipt.acceptance_passed is not True
            or not receipt.runtime_session_id
            or not receipt.process_pid
            or receipt.process_start_identity in {None, "", "unknown"}
            or pid_is_alive(receipt.process_pid)
            or _capture_commands(root, receipt)[0] != (command,)
        ):
            return False
    return bool(
        not cp.uncertainty
        and cp.last_completed_step
        and cp.process_pid
        and cp.process_start_identity
        and cp.process_start_identity != "unknown"
        and not pid_is_alive(cp.process_pid)
        and holder_liveness(cp)[0] is Liveness.GONE
        and attempt is not None
        and cp.identity.worker_id == attempt.agent_id
        and cp.identity.session_id == attempt.runtime_session_id
        and attempt.step_id == cp.last_completed_step
        and attempt.process_pid == cp.process_pid
        and attempt.process_start_identity == cp.process_start_identity
        and attempt.exit_status == 0
        and attempt.confidence is ExecutionConfidence.CONFIRMED
        and attempt.acceptance_passed is True
        and cp.commands
        and cp.commands[-1].exit_status == 0
    )


def final_acceptance_ready(root: Path, task: ProgramTask, state: ProgramStateRecord) -> bool:
    """Permit observed final acceptance reconciliation, never a worker launch."""
    envelope = load_envelope(root, task.task_id)
    cp = load_checkpoint(root, task.task_id)
    if (
        envelope is None
        or cp is None
        or not task.execution_steps
        or unobserved_wall_attempts(state, task.task_id)
    ):
        return False
    if (
        cp.envelope_digest != envelope.digest()
        or cp.terminal
        or cp.replay_class is not ReplayClass.CHECKPOINT_RESUMABLE
        or cp.last_completed_step != task.execution_steps[-1].step_id
        or envelope.checkpoint_policy.steps != tuple(s.step_id for s in task.execution_steps)
        or any(e.confirmed is not True for e in cp.external_effects)
        or not completed_boundary(root, task, state)
    ):
        return False
    consumed = consumed_for_task(state, task.task_id, cp)
    budgets = envelope.budgets
    # Exactly spent worker reservations do not prohibit controller acceptance;
    # exceeding any bound still refuses. Final checks do require remaining
    # wall time. Pause gates worker dispatch, not this no-launch settlement.
    return (
        consumed.attempts <= budgets.max_attempts
        and consumed.launches <= budgets.max_launches
        and consumed.wall_seconds < budgets.max_wall_seconds
        and consumed.model_calls <= budgets.max_model_calls
        and consumed.estimated_cost_usd <= budgets.max_estimated_cost_usd
    )


def record_intent(
    root: Path,
    task: ProgramTask,
    attempt: AttemptRecord,
    state: ProgramStateRecord,
    workspace: Path,
    *,
    revision_observed: bool = True,
) -> None:
    envelope = load_envelope(root, task.task_id)
    assert envelope is not None  # selected_step validated before any dispatch
    previous = load_checkpoint(root, task.task_id)
    consumed = previous.consumed_budget if previous else ConsumedBudget()
    observed = consumed_for_task(state, task.task_id, previous)
    consumed = consumed.model_copy(
        update={
            "wall_seconds": observed.wall_seconds,
            "estimated_cost_usd": observed.estimated_cost_usd,
        }
    )
    cp = ContinuationCheckpoint(
        identity=ExecutionIdentity(
            task_id=task.task_id,
            worker_id=attempt.agent_id,
            session_id=attempt.runtime_session_id or attempt.attempt_id,
            attempt_id=attempt.attempt_id,
        ),
        envelope_digest=envelope.digest(),
        program_id=state.program_id,
        sequence=previous.sequence + 1 if previous else 1,
        last_completed_step=previous.last_completed_step if previous else None,
        next_action=f"reconcile unconfirmed step {attempt.step_id}",
        worktree_path=str(workspace),
        git_head=envelope.candidate_head,
        git_tree=envelope.candidate_tree,
        replay_class=envelope.replay_class,
        lease=_lease_snapshot(
            root, task.task_id, session_id=attempt.runtime_session_id or attempt.attempt_id
        ),
        consumed_budget=consumed.model_copy(
            update={
                "attempts": max(consumed.attempts + 1, state.tasks[task.task_id].attempts),
                "launches": max(consumed.launches + 1, state.tasks[task.task_id].launches + 1),
            }
        ),
        commands=previous.commands if previous else (),
        artifacts=previous.artifacts if previous else (),
        uncertainty=(
            ()
            if envelope.replay_class is ReplayClass.READ_ONLY_REPLAYABLE
            else (f"step {attempt.step_id} has dispatch intent but no observed completion",)
        ),
        deadline_utc=envelope.deadline_utc,
    )
    if not revision_observed:
        from project_atlas.orchestration.program.candidate import UNVERSIONED_FIXTURE_BOUNDARY

        cp.truth_boundary += " / " + UNVERSIONED_FIXTURE_BOUNDARY
    persist_checkpoint(root, cp)


def record_completion(
    root: Path, task: ProgramTask, attempt: AttemptRecord, workspace: Path, duration: float
) -> None:
    previous = load_checkpoint(root, task.task_id)
    if previous is None or previous.identity.attempt_id != attempt.attempt_id:
        raise ProgramError("step completion has no matching intent", code="STEP_INTENT_MISMATCH")
    commands, command_capture = _capture_commands(root, attempt)
    if not commands or commands[-1].exit_status != 0:
        raise ProgramError(
            "step completion has no observed successful command", code="STEP_COMMAND_MISSING"
        )
    artifacts, artifact_capture = _capture_artifacts(task, attempt, workspace)
    state = load_state(root)
    if state is None:
        raise ProgramError(
            "step completion lost its durable attempt state", code="STEP_STATE_MISSING"
        )
    consumed = consumed_for_task(state, task.task_id, previous)
    cp = previous.model_copy(
        update={
            "sequence": previous.sequence + 1,
            "recorded_at": utc_now(),
            "last_completed_step": attempt.step_id,
            "next_action": "dispatch next approved step, or evaluate final task acceptance",
            "uncertainty": (),
            "process_pid": attempt.process_pid,
            "process_start_identity": attempt.process_start_identity,
            "commands": (*previous.commands, *commands),
            "artifacts": (*previous.artifacts, *artifacts),
            "execution_capture": ExecutionCapture.OBSERVED,
            "capture": ExecutionCaptureReport(
                commands=command_capture,
                artifacts=artifact_capture,
                changed_files=_CHANGED_FILES_UNAVAILABLE,
            ),
            "consumed_budget": consumed.model_copy(
                update={
                    "wall_seconds": max(
                        consumed.wall_seconds,
                        previous.consumed_budget.wall_seconds + max(0.0, duration),
                    ),
                }
            ),
        }
    )
    persist_checkpoint(root, cp)
