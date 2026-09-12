"""Restart reconciliation over durable checkpoints. Nothing is ever assumed.

``recovery.py`` answers a narrower question -- what may be done with one
interrupted *attempt*, from its phase and its process liveness. This module
answers the question a replacement session actually asks: **given the durable
checkpoint for this task, what is the next safe action, if any?**

The difference matters because the two inputs are different. An attempt record
knows which phase it reached. A checkpoint knows which *step* completed, what
it changed, what it may have done outside this machine, and what budget is
left. A task can be perfectly healthy at the attempt level and still be
unresumable because its last step recorded an unconfirmed external effect.

The invariants, in the order they are enforced:

1. A ``COMPLETED`` task is never replayed. Not "usually not" -- the check is
   first, before liveness, before leases, before budgets, because every other
   branch below could otherwise reach a launch.
2. An unconfirmed external effect is quarantined as ``RECONCILE_REQUIRED``.
   Automatic replay of an effect nobody can see is the failure this whole
   layer exists to prevent.
3. Checkpoint-safe work resumes at the step after the last one recorded
   complete -- never at the top, because the top would redo the steps that
   already landed.
4. Work is reacquired only after the previous lease has expired *and* the
   previous holder's process identity has been checked. A holder that stopped
   answering is not a holder that stopped running.
5. Authority is rechecked immediately before dispatch, by the caller, using
   ``continuation.validate_envelope_for_dispatch``. This module refuses to
   return a launch disposition without having been handed that check's result.
6. Corrupt, contradictory or incomplete state fails closed. It is never
   repaired here, and it is never downgraded to "start from scratch" -- both
   would be this layer deciding what a previous execution had done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from project_atlas.orchestration.program.adapters.base import pid_is_alive, process_start_identity
from project_atlas.orchestration.program.continuation import (
    CheckpointError,
    ContinuationCheckpoint,
    ReplayClass,
    TaskEnvelope,
    load_checkpoint,
    load_envelope,
)
from project_atlas.orchestration.program.models import ProgramError
from project_atlas.orchestration.program.recovery import Liveness


class ReconciliationError(ProgramError):
    code = "RECONCILIATION_ERROR"


class Disposition(StrEnum):
    """What a replacement session may do with one task, after reconciliation."""

    #: No durable record exists and the task has never run. Start at step one.
    START_FRESH = "START_FRESH"
    #: A record exists and the work is safe to run again from the top.
    RESTART_FROM_TOP = "RESTART_FROM_TOP"
    #: Continue at the step after the last one recorded complete.
    RESUME_AT_NEXT_STEP = "RESUME_AT_NEXT_STEP"
    #: A worker of ours is demonstrably still running. Leave it alone.
    WORKER_STILL_RUNNING = "WORKER_STILL_RUNNING"
    #: Finished and sealed. Zero launches, now and at every future restart.
    ALREADY_COMPLETE = "ALREADY_COMPLETE"
    #: Quarantined. An operator decides; nothing automatic happens.
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"
    #: A person must decide something before this work can proceed at all.
    HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"
    #: The lease is still held by a live holder that is not us.
    LEASE_HELD_ELSEWHERE = "LEASE_HELD_ELSEWHERE"
    #: The durable state is unusable. Nothing proceeds and nothing is repaired.
    FAIL_CLOSED = "FAIL_CLOSED"


#: Dispositions that permit an adapter launch. Everything else must not reach
#: one. Kept as an explicit set so a new member of ``Disposition`` cannot
#: become launchable by being added -- it has to be added here too, on purpose.
LAUNCHABLE: Final[frozenset[Disposition]] = frozenset(
    {
        Disposition.START_FRESH,
        Disposition.RESTART_FROM_TOP,
        Disposition.RESUME_AT_NEXT_STEP,
    }
)


@dataclass(frozen=True)
class ReconciliationVerdict:
    """One task's disposition, with the reason and the evidence behind it."""

    task_id: str
    disposition: Disposition
    #: The replay class this verdict was reached under. For a derived class
    #: (COMPLETED, HUMAN_DECISION_REQUIRED) this differs from the envelope's
    #: declaration, which is the point: the finding overrides the declaration.
    replay_class: ReplayClass
    reason: str
    resume_step: str | None = None
    #: Every observation the verdict rests on, so it can be audited without
    #: re-deriving it. Deliberately plain strings: this is read by people.
    evidence: tuple[str, ...] = field(default_factory=tuple)

    @property
    def launchable(self) -> bool:
        return self.disposition in LAUNCHABLE


def holder_liveness(
    checkpoint: ContinuationCheckpoint,
) -> tuple[Liveness, str]:
    """Is the process that wrote this checkpoint still running?

    Reuses the three-valued answer rather than a boolean, for the reason
    ``recovery.Liveness`` documents: "we recorded no identity" and "the process
    is demonstrably gone" must not produce the same value, because a caller
    will turn the second one into a launch.
    """
    pid = checkpoint.process_pid
    recorded = checkpoint.process_start_identity
    if pid is None or pid <= 0:
        return Liveness.UNKNOWN, "the checkpoint records no process identity"
    if not pid_is_alive(pid):
        return Liveness.GONE, f"pid {pid} is not running"
    if not recorded or recorded == "unknown":
        return (
            Liveness.UNKNOWN,
            f"pid {pid} is running but the checkpoint recorded no start "
            "identity, so it cannot be told apart from a reused pid",
        )
    live = process_start_identity(pid)
    if not live or live == "unknown":
        return (
            Liveness.UNKNOWN,
            f"pid {pid} is running but this platform reports no start identity "
            "to compare against the recorded one",
        )
    if live == recorded:
        return (
            Liveness.ALIVE,
            f"pid {pid} is running and its start identity matches the one in "
            "the checkpoint",
        )
    return (
        Liveness.GONE,
        f"pid {pid} is running under a different start identity; the recorded "
        "process exited and the pid was reused",
    )


def _unconfirmed_effects(checkpoint: ContinuationCheckpoint) -> tuple[str, ...]:
    """Receipts whose effect nobody has established either way."""
    return tuple(
        f"{receipt.kind}:{receipt.receipt_id} -- {receipt.description}"
        for receipt in checkpoint.external_effects
        if receipt.confirmed is None
    )


def reconcile_task(
    *,
    envelope: TaskEnvelope,
    checkpoint: ContinuationCheckpoint | None,
    our_worker_id: str,
    now: datetime | None = None,
) -> ReconciliationVerdict:
    """Decide what may happen next for one task. Pure, given its inputs.

    Kept free of I/O so the whole decision table is testable without a
    filesystem, and so the ordering of the invariants is visible in one place
    rather than spread across the callers that happen to hit them.
    """
    moment = now or datetime.now(UTC)
    evidence: list[str] = []

    if checkpoint is None:
        # Never run. Not "probably never run": the absence of a checkpoint is
        # only ever reached through `load_checkpoint`, which raises rather than
        # returning None for anything present-but-unusable.
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.START_FRESH,
            replay_class=envelope.replay_class,
            reason="no durable checkpoint exists for this task",
            evidence=("no checkpoint file",),
        )

    if checkpoint.envelope_digest != envelope.digest():
        # The authority under which the work was started is not the authority
        # now on disk. Silently continuing would execute the remainder of a
        # task under terms nobody approved for it.
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.FAIL_CLOSED,
            replay_class=envelope.replay_class,
            reason=(
                "the checkpoint was written under a different envelope than the "
                "one now on disk; the authority for this work changed mid-flight"
            ),
            evidence=(
                f"checkpoint envelope_digest={checkpoint.envelope_digest[:16]}...",
                f"current envelope digest={envelope.digest()[:16]}...",
            ),
        )

    # INVARIANT 1. Completed work is never replayed, and this is checked before
    # anything that could lead to a launch.
    if checkpoint.terminal and checkpoint.replay_class is ReplayClass.COMPLETED:
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.ALREADY_COMPLETE,
            replay_class=ReplayClass.COMPLETED,
            reason="the task is recorded complete; completed work is never replayed",
            evidence=(
                f"terminal checkpoint sequence {checkpoint.sequence}",
                f"last completed step {checkpoint.last_completed_step}",
                f"{len(checkpoint.artifacts)} sealed artifact(s)",
            ),
        )

    if checkpoint.terminal and (
        checkpoint.replay_class is ReplayClass.HUMAN_DECISION_REQUIRED
    ):
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.HUMAN_DECISION_REQUIRED,
            replay_class=ReplayClass.HUMAN_DECISION_REQUIRED,
            reason=(
                "the task stopped on a decision that is not this layer's to "
                "make: " + (checkpoint.blockers[0] if checkpoint.blockers else "unstated")
            ),
            evidence=checkpoint.blockers or ("no blocker text recorded",),
        )

    # A live holder outranks everything below: whatever the record says, a
    # running worker of ours must not acquire a second one beside it.
    liveness, why = holder_liveness(checkpoint)
    evidence.append(why)
    if liveness is Liveness.ALIVE:
        if checkpoint.identity.worker_id == our_worker_id:
            return ReconciliationVerdict(
                task_id=envelope.task_id,
                disposition=Disposition.WORKER_STILL_RUNNING,
                replay_class=envelope.replay_class,
                reason="a worker of ours is still running this task",
                evidence=tuple(evidence),
            )
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.LEASE_HELD_ELSEWHERE,
            replay_class=envelope.replay_class,
            reason=(
                f"worker {checkpoint.identity.worker_id} is still running this "
                "task and is not us"
            ),
            evidence=tuple(evidence),
        )

    # INVARIANT 2. An effect nobody can see is quarantined, whatever else is
    # true. Checked before the resume branches, because a CHECKPOINT_RESUMABLE
    # task that emitted an unconfirmed effect at its last step is exactly the
    # case where "resume at the next step" would skip a reconciliation.
    unconfirmed = _unconfirmed_effects(checkpoint)
    if unconfirmed:
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.RECONCILE_REQUIRED,
            replay_class=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT,
            reason=(
                "the last execution recorded an external effect whose outcome "
                "is unknown; it is quarantined rather than repeated"
            ),
            evidence=(*evidence, *unconfirmed),
        )

    if checkpoint.uncertainty:
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.RECONCILE_REQUIRED,
            replay_class=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT,
            reason=(
                "the last execution recorded unresolved uncertainty about what "
                "it did"
            ),
            evidence=(*evidence, *checkpoint.uncertainty),
        )

    if envelope.replay_class is ReplayClass.UNCERTAIN_EXTERNAL_EFFECT and (
        not checkpoint.terminal
    ):
        # The class is declared, the execution did not finish, and no receipt
        # says what happened. The absence of a receipt is not evidence that
        # nothing happened -- the process may have died before writing one.
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.RECONCILE_REQUIRED,
            replay_class=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT,
            reason=(
                "this task is declared capable of an effect outside our "
                "observation and its last execution did not reach a terminal "
                "checkpoint; a missing receipt is not proof of a missing effect"
            ),
            evidence=tuple(evidence),
        )

    # INVARIANT 4. Reacquisition needs expiry AND an identity check. The
    # identity check already happened above (liveness); expiry is here.
    if checkpoint.lease is not None and not checkpoint.lease.expired(moment):
        if checkpoint.lease.holder_worker_id != our_worker_id:
            return ReconciliationVerdict(
                task_id=envelope.task_id,
                disposition=Disposition.LEASE_HELD_ELSEWHERE,
                replay_class=envelope.replay_class,
                reason=(
                    f"the lease is held by {checkpoint.lease.holder_worker_id} "
                    f"until {checkpoint.lease.expires_at} and has not expired"
                ),
                evidence=(*evidence, f"lease {checkpoint.lease.lease_id}"),
            )
        evidence.append(
            f"lease {checkpoint.lease.lease_id} is ours and still valid until "
            f"{checkpoint.lease.expires_at}"
        )
    elif checkpoint.lease is not None:
        evidence.append(
            f"lease {checkpoint.lease.lease_id} expired at "
            f"{checkpoint.lease.expires_at}; its holder's process is "
            f"{liveness.value}"
        )

    if envelope.deadline_utc is not None:
        evidence.append(f"envelope deadline {envelope.deadline_utc}")

    blown = checkpoint.consumed_budget.exceeds(envelope.budgets)
    if blown is not None:
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.HUMAN_DECISION_REQUIRED,
            replay_class=ReplayClass.HUMAN_DECISION_REQUIRED,
            reason=(
                f"the task's budget is spent ({blown}); raising a budget is an "
                "operator decision, not a retry"
            ),
            evidence=tuple(evidence),
        )

    # INVARIANT 3. Checkpoint-safe work resumes at the next uncompleted step.
    if envelope.replay_class is ReplayClass.CHECKPOINT_RESUMABLE:
        try:
            next_step = envelope.next_step_after(checkpoint.last_completed_step)
        except CheckpointError as exc:
            return ReconciliationVerdict(
                task_id=envelope.task_id,
                disposition=Disposition.FAIL_CLOSED,
                replay_class=envelope.replay_class,
                reason=str(exc),
                evidence=tuple(evidence),
            )
        if next_step is None:
            # Every step is recorded complete but no terminal checkpoint was
            # sealed. This is incomplete state, not finished work: the seal is
            # what makes "complete" a fact, and inventing it here would be this
            # layer certifying its own predecessor.
            return ReconciliationVerdict(
                task_id=envelope.task_id,
                disposition=Disposition.RECONCILE_REQUIRED,
                replay_class=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT,
                reason=(
                    "every step is recorded complete but no terminal checkpoint "
                    "was sealed; the work may or may not have finished and this "
                    "layer will not certify it"
                ),
                evidence=tuple(evidence),
            )
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.RESUME_AT_NEXT_STEP,
            replay_class=ReplayClass.CHECKPOINT_RESUMABLE,
            reason=(
                f"steps up to {checkpoint.last_completed_step or 'none'} are "
                f"recorded complete; continuing at {next_step}"
            ),
            resume_step=next_step,
            evidence=tuple(evidence),
        )

    if envelope.replay_class in (
        ReplayClass.READ_ONLY_REPLAYABLE,
        ReplayClass.IDEMPOTENT_MUTATION,
    ):
        return ReconciliationVerdict(
            task_id=envelope.task_id,
            disposition=Disposition.RESTART_FROM_TOP,
            replay_class=envelope.replay_class,
            reason=(
                f"the task is declared {envelope.replay_class.value}, so running "
                "it again from the first step is indistinguishable from having "
                "run it once"
            ),
            evidence=tuple(evidence),
        )

    # Unreachable while the enum is closed and every declarable member is
    # handled above. Kept as a refusal rather than an assertion because the
    # correct behaviour for an unhandled class is to stop, not to guess.
    return ReconciliationVerdict(  # pragma: no cover - defensive
        task_id=envelope.task_id,
        disposition=Disposition.FAIL_CLOSED,
        replay_class=envelope.replay_class,
        reason=f"no reconciliation rule for replay class {envelope.replay_class}",
        evidence=tuple(evidence),
    )


def reconcile_root(
    root: Path, *, our_worker_id: str, now: datetime | None = None
) -> tuple[ReconciliationVerdict, ...]:
    """Reconcile every task that has an envelope under one state root.

    A task whose durable state cannot be read yields a ``FAIL_CLOSED`` verdict
    rather than raising, so one corrupt record does not hide the disposition of
    every other task. The refusal is still a refusal: ``FAIL_CLOSED`` is not
    launchable.
    """
    from project_atlas.orchestration.program.continuation import list_envelopes

    verdicts: list[ReconciliationVerdict] = []
    for envelope in list_envelopes(root):
        try:
            checkpoint = load_checkpoint(root, envelope.task_id)
        except CheckpointError as exc:
            verdicts.append(
                ReconciliationVerdict(
                    task_id=envelope.task_id,
                    disposition=Disposition.FAIL_CLOSED,
                    replay_class=envelope.replay_class,
                    reason=f"durable state is unusable: {exc}",
                    evidence=(getattr(exc, "code", "CHECKPOINT_INVALID"),),
                )
            )
            continue
        verdicts.append(
            reconcile_task(
                envelope=envelope,
                checkpoint=checkpoint,
                our_worker_id=our_worker_id,
                now=now,
            )
        )
    return tuple(verdicts)


def reconcile_one(
    root: Path, task_id: str, *, our_worker_id: str, now: datetime | None = None
) -> ReconciliationVerdict:
    """Reconcile a single task, by id."""
    envelope = load_envelope(root, task_id)
    if envelope is None:
        raise ReconciliationError(
            f"no task envelope recorded for {task_id}; there is no authority to "
            "reconcile against",
            code="ENVELOPE_MISSING",
        )
    try:
        checkpoint = load_checkpoint(root, task_id)
    except CheckpointError as exc:
        return ReconciliationVerdict(
            task_id=task_id,
            disposition=Disposition.FAIL_CLOSED,
            replay_class=envelope.replay_class,
            reason=f"durable state is unusable: {exc}",
            evidence=(getattr(exc, "code", "CHECKPOINT_INVALID"),),
        )
    return reconcile_task(
        envelope=envelope,
        checkpoint=checkpoint,
        our_worker_id=our_worker_id,
        now=now,
    )
