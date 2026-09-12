"""Turning a program run into durable envelopes and checkpoints.

Without this, the continuation layer is a set of correct mechanisms that
nothing feeds: a program executed through the dispatcher produces `state.json`
and `events.jsonl`, and a replacement session asking for a capsule is told
"no task envelopes recorded" -- which is true, and useless.

So the dispatcher materialises an **envelope per approved task before the
program runs**, and **projects a checkpoint per task after it stops**. Both are
derivations from records that already exist; neither invents anything.

What this DOES give: a replacement session, on a different process and after a
reboot, reconstructs every task's authority, its disposition, its artifacts and
its next concrete action from files.

What it does NOT give, stated plainly because the difference matters: these
checkpoints are written at **program boundaries**, not after every step inside a
worker. A task that wants step-level resume declares steps in its envelope's
checkpoint policy and writes its own checkpoints as it goes -- the mechanism is
the same `persist_checkpoint`, and `reconciliation` treats both identically.
Boundary checkpoints are enough to answer "may this run again?"; they are not
enough to answer "which of its five steps already landed?", and this module
does not pretend otherwise.

The replay class for a task that does not declare one is deliberately the
**most cautious** available: `UNCERTAIN_EXTERNAL_EFFECT`. An unannotated
mutating task interrupted mid-flight then demands reconciliation rather than
being replayed. Defaulting the other way would make silence mean "safe to
repeat", and silence is exactly what an unannotated task is.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.orchestration.autonomy.lease_projection import (
    ProjectionError,
    active_rows,
    load_projection,
)
from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program.continuation import (
    CheckpointError,
    CheckpointPolicy,
    ConsumedBudget,
    ContinuationCheckpoint,
    ExecutionCapture,
    ExecutionIdentity,
    LeaseSnapshot,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    envelope_from_task,
    load_checkpoint,
    load_envelope,
    persist_checkpoint,
    persist_envelope,
    utc_now,
)
from project_atlas.orchestration.program.loader import LoadedProgram
from project_atlas.orchestration.program.models import ExecutionConfidence, ProgramTask
from project_atlas.orchestration.program.store import AttemptRecord, ProgramStateRecord

#: Task states that mean the work is finished and sealed.
_DONE: frozenset[NodeState] = frozenset({NodeState.CERTIFIED, NodeState.CLOSED})
#: Task states that mean a person has to decide before anything else happens.
_STUCK: frozenset[NodeState] = frozenset({NodeState.BLOCKED, NodeState.OWNER_HELD})


def replay_class_for(task: ProgramTask) -> ReplayClass:
    """The replay class a task gets when it does not declare one.

    Three cases, and the ordering is the argument:

    1. A task that declares its effect safe to repeat after a crash with no
       launch evidence has already told us it is idempotent. Believe it -- that
       flag is the existing, reviewed way for a program to say so.
    2. A task with no mutation paths writes nothing but its own evidence.
    3. Everything else is treated as capable of an effect we cannot see. That
       is the cautious answer, and it is the right default because the
       alternative reading of silence is "safe to repeat".
    """
    if task.retry_safe_when_no_launch_evidence:
        return ReplayClass.IDEMPOTENT_MUTATION
    if not task.mutation_paths:
        return ReplayClass.READ_ONLY_REPLAYABLE
    return ReplayClass.UNCERTAIN_EXTERNAL_EFFECT


def materialise_envelopes(
    loaded: LoadedProgram,
    root: Path,
    *,
    candidate_head: str,
    candidate_tree: str,
) -> tuple[TaskEnvelope, ...]:
    """Write one envelope per approved task, idempotently.

    An existing envelope is left alone rather than rewritten. Rewriting it
    would move the authority a running attempt was started under, and
    ``reconcile_task`` would then -- correctly -- declare that authority had
    changed mid-flight and refuse to continue. The one thing that must not
    happen on every tick is the layer invalidating its own checkpoints.
    """
    written: list[TaskEnvelope] = []
    for task in loaded.program.tasks:
        existing = load_envelope(root, task.task_id)
        if existing is not None:
            written.append(existing)
            continue
        profile = loaded.effective_profile(task.task_id)
        limits = profile.limits
        envelope = envelope_from_task(
            task,
            program=loaded.program,
            candidate_head=candidate_head,
            candidate_tree=candidate_tree,
            worker_id=profile.agent_id,
            replay_class=replay_class_for(task),
            budgets=TaskBudgets(
                max_attempts=loaded.program.limits.max_attempts_per_task,
                max_launches=max(1, loaded.program.limits.max_task_launches),
                max_wall_seconds=loaded.program.limits.max_task_seconds,
                # Zero, always, while model-backed dispatch is disabled. Taken
                # from the switch and not from the profile's own cost ceiling:
                # a profile that permits spend is not a grant to spend here.
                max_model_calls=0,
                max_estimated_cost_usd=float(limits.max_estimated_cost_usd or 0.0),
            ),
            checkpoint_policy=CheckpointPolicy(steps=()),
            forbidden_paths=(),
            allowed_actions=(),
            # Recorded on every envelope, for a reader rather than for a gate:
            # these are the acts this package never performs, and an envelope
            # that listed none would leave that to be inferred.
            forbidden_actions=("MERGE", "PUSH", "RELEASE", "CREDENTIAL_CHANGE"),
        )
        persist_envelope(root, envelope)
        written.append(envelope)
    return tuple(written)


def _lease_snapshot(root: Path, task_id: str, *, session_id: str) -> LeaseSnapshot | None:
    """The ACTIVE projected lease for a task, as a checkpoint snapshot.

    ``expires_at`` is the honest problem here: the projection row carries a
    terminal condition, not a wall-clock expiry. Rather than invent one, the
    snapshot records a far-future expiry, which makes the checkpoint say "this
    lease has not expired" -- and reconciliation then falls through to the
    process identity check, which is the evidence that actually decides whether
    the holder is gone. An invented near expiry would let a successor take work
    from a live holder on the strength of a number nobody measured.
    """
    try:
        projection = load_projection(root)
    except ProjectionError:
        return None
    for row in active_rows(projection):
        if row.package_id != task_id:
            continue
        return LeaseSnapshot(
            lease_id=row.lease_id,
            holder_worker_id=row.agent_id,
            holder_session_id=session_id,
            granted_at=utc_now(),
            expires_at="2099-01-01T00:00:00.000Z",
        )
    return None


def _attempt_for(state: ProgramStateRecord, task_id: str) -> AttemptRecord | None:
    record = state.tasks.get(task_id)
    if record is None or record.last_attempt_id is None:
        return None
    return state.attempts.get(record.last_attempt_id)


def project_checkpoints(
    loaded: LoadedProgram,
    root: Path,
    *,
    state: ProgramStateRecord,
    session_id: str,
    worktree: Path,
    git_head: str,
    git_tree: str,
) -> tuple[ContinuationCheckpoint, ...]:
    """Project one checkpoint per task from durable supervisor state.

    Every value comes from a record the supervisor already wrote. Nothing here
    observes a process, evaluates acceptance, or decides an outcome -- it
    projects, and a projection that disagreed with its source would be a second
    opinion nobody asked for.
    """
    written: list[ContinuationCheckpoint] = []
    for task in loaded.program.tasks:
        envelope = load_envelope(root, task.task_id)
        if envelope is None:
            continue
        record = state.tasks.get(task.task_id)
        if record is None:
            continue
        attempt = _attempt_for(state, task.task_id)

        previous = None
        try:
            previous = load_checkpoint(root, task.task_id)
        except CheckpointError:
            # A checkpoint we cannot read must not be overwritten by a fresh
            # projection: the unreadable record is evidence of something, and
            # replacing it would destroy the only trace of it. Reconciliation
            # already fails closed on it.
            #
            # This is the SECOND of two mechanisms, and measured as such rather
            # than assumed: removing it alone changes nothing, because
            # `persist_checkpoint` refuses a sequence at or below the one on
            # disk and an unreadable record still yields sequence 1. Removing
            # BOTH lets the projection clobber the tampered file. Kept because
            # it refuses earlier and for the right reason -- the sequence check
            # is defending a different property and would stop defending this
            # one the moment a projection legitimately carried a higher
            # sequence.
            continue
        sequence = (previous.sequence + 1) if previous is not None else 1

        terminal = record.state in _DONE or record.state in _STUCK
        if record.state in _DONE:
            replay = ReplayClass.COMPLETED
            next_action = f"nothing; {task.task_id} is complete and is never replayed"
        elif record.state in _STUCK:
            replay = ReplayClass.HUMAN_DECISION_REQUIRED
            next_action = (
                f"a person decides what happens to {task.task_id}; "
                f"it is {record.state.value}"
            )
        else:
            replay = envelope.replay_class
            next_action = (
                f"reconcile {task.task_id} (state {record.state.value}) before "
                "any dispatch"
            )

        # ``record.reason`` is the supervisor's note for whatever state the
        # task is in -- including "every acceptance condition observed to
        # hold". Carrying that into ``blockers`` unconditionally would label a
        # success as a blocker in the capsule, which is worse than saying
        # nothing: a reader scanning for blockers would find one on every
        # completed task. It is a blocker only when the task is actually stuck.
        blockers: tuple[str, ...] = ()
        if record.state in _STUCK and record.reason:
            blockers = (record.reason[:512],)
        uncertainty: tuple[str, ...] = ()
        if attempt is not None and attempt.confidence is ExecutionConfidence.UNCERTAIN:
            uncertainty = (
                f"attempt {attempt.attempt_id} reached phase "
                f"{attempt.phase.value} with an uncertain outcome",
            )

        checkpoint = ContinuationCheckpoint(
            identity=ExecutionIdentity(
                task_id=task.task_id,
                worker_id=envelope.worker_id,
                session_id=session_id,
                attempt_id=(
                    attempt.attempt_id
                    if attempt is not None
                    else f"{task.task_id}.no-attempt.{sequence}"
                ),
            ),
            envelope_digest=envelope.digest(),
            program_id=loaded.program.program_id,
            sequence=sequence,
            last_completed_step=None,
            next_action=next_action,
            worktree_path=str(worktree),
            git_head=git_head,
            git_tree=git_tree,
            process_pid=attempt.process_pid if attempt is not None else None,
            process_start_identity=(
                attempt.process_start_identity if attempt is not None else None
            ),
            lease=_lease_snapshot(root, task.task_id, session_id=session_id),
            consumed_budget=ConsumedBudget(
                attempts=record.attempts,
                launches=record.launches,
                model_calls=0,
                estimated_cost_usd=(
                    float(attempt.estimated_cost_usd or 0.0)
                    if attempt is not None
                    else 0.0
                ),
            ),
            # G4, stated rather than left to be inferred from empty lists: this
            # projection writes at PROGRAM BOUNDARIES and never observes a
            # worker, so it cannot report what changed, what ran, or what was
            # produced. Marking it NOT_CAPTURED is the whole of the honest
            # answer -- reconstructing commands from a workspace diff would be
            # inventing a history nobody recorded.
            execution_capture=ExecutionCapture.NOT_CAPTURED,
            blockers=blockers,
            uncertainty=uncertainty,
            replay_class=replay,
            terminal=terminal,
        )
        try:
            written.append(persist_checkpoint(root, checkpoint))
        except CheckpointError:
            # A sequence regression here means somebody else wrote a checkpoint
            # for this task while the program ran. Theirs stands; a projection
            # is the weaker record and must not overwrite a first-hand one.
            continue
    return tuple(written)
