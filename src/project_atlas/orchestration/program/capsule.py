"""The continuation capsule: what a replacement session is handed instead of a chat.

The requirement this satisfies, stated exactly: *a new session must receive a
bounded machine-generated continuation capsule from durable state, and must not
depend on prior chat history.*

So the capsule is generated from files and nothing else. It reads the approved
program, the task envelopes, the sealed checkpoints, the reconciliation
verdicts, the open decision queue and the dispatcher heartbeat. It reads no
transcript, takes no argument that a previous session could have written in
prose, and contains no instruction to the reader beyond the next concrete
action already recorded in a checkpoint.

Two properties are enforced rather than intended:

**Bounded.** ``CAPSULE_MAX_BYTES`` is a hard ceiling on the rendered text. A
capsule that grows with the history it summarises eventually cannot be handed
to anything, which defeats its purpose. When content is dropped to fit, the
rendered capsule says so, in the place the content would have been. Silent
truncation would be worse than no capsule: a reader cannot tell a short list
from a truncated one.

**Authority-free.** The capsule reports what a task is permitted to do; it
does not permit anything. ``CAPSULE_GENERATED != AUTHORITY_GRANTED``. A
replacement session that reads a capsule still has to pass
``validate_envelope_for_dispatch`` before it may launch anything, and that
check reads the envelope on disk, not the capsule.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.program.approved_queue import load_queue
from project_atlas.orchestration.program.continuation import (
    CAPSULE_MAX_BYTES,
    CAPSULE_NAME,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    ContinuationCheckpoint,
    TaskEnvelope,
    list_envelopes,
    load_checkpoint,
    utc_now,
)
from project_atlas.orchestration.program.decisions import (
    DecisionStatus,
    decisions_dir,
    list_decisions,
)
from project_atlas.orchestration.program.path_safety import (
    ContainmentError,
    check_children,
    checked_path,
    trusted_root,
)
from project_atlas.orchestration.program.reconciliation import (
    Disposition,
    ReconciliationVerdict,
    completed_program_task_ids,
    prior_execution_evidence,
    reconcile_task,
)
from project_atlas.orchestration.program.resident import dispatcher_dir, read_heartbeat
from project_atlas.orchestration.program.store import write_json_atomic

#: How many of each list survive into the capsule. Chosen so a capsule with
#: every list full still renders inside the byte ceiling with room for the
#: authority block, which is the part that must never be the thing dropped.
_MAX_TASKS: Final[int] = 24
_MAX_EVIDENCE: Final[int] = 6
_MAX_ARTIFACTS: Final[int] = 8
_MAX_DECISIONS: Final[int] = 12
_TRUNCATION_MARK: Final[str] = "... TRUNCATED"


class CapsuleTask(BaseModel):
    """One task, as a replacement session needs to see it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    #: Which state root this task's envelope and checkpoint were read from.
    #: Present because a dispatcher's own root and a program's root can differ,
    #: and a reader that cannot see which is which cannot find the records.
    state_root: str
    disposition: Disposition
    replay_class: str
    reason: str
    next_action: str
    resume_step: str | None = None
    last_completed_step: str | None = None
    #: Authority, reported. Never granted by being reported.
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    candidate_head: str = ""
    candidate_tree: str = ""
    deadline_utc: str | None = None
    budget_remaining: dict[str, float] = Field(default_factory=dict)
    blockers: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    #: One line per observed command: argv, exit status, source record.
    commands: tuple[str, ...] = ()
    #: Whether this task's execution detail was observed at all. G4: empty
    #: artifact/command/changed-file lists mean "nobody looked" when this is
    #: NOT_CAPTURED, and "nothing happened" only when it is OBSERVED.
    execution_capture: str = "NOT_CAPTURED"
    #: Per-field capture statement, keyed commands/artifacts/changed_files,
    #: each {status, reason, source}. Copied from the checkpoint, never derived
    #: from whether the lists above happen to be empty.
    capture: dict[str, dict[str, str]] = Field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    launchable: bool = False
    truncated: bool = False


class ContinuationCapsule(BaseModel):
    """Everything durable that a replacement session needs, and nothing else."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    generated_at: str = Field(default_factory=utc_now)
    state_root: str
    #: Who the capsule is being generated for. Recorded so a capsule read by a
    #: different principal is visibly a capsule for somebody else.
    for_worker_id: str
    dispatcher: dict[str, Any] = Field(default_factory=dict)
    queue: dict[str, Any] = Field(default_factory=dict)
    tasks: tuple[CapsuleTask, ...] = ()
    #: Every state root this capsule actually looked in, in scan order. A
    #: reader can tell "there is nothing to resume" from "you did not point me
    #: at the root the work is in" only if this is visible.
    state_roots_scanned: tuple[str, ...] = ()
    #: Set when the dispatcher's own root holds no task records but an admitted
    #: program keeps its records elsewhere. Silence here was a real defect: a
    #: replacement session read "no task envelopes recorded" off a perfectly
    #: healthy program and concluded there was nothing to do.
    root_split_note: str = ""
    open_decisions: tuple[dict[str, Any], ...] = ()
    #: Set when any list was shortened to fit. Never silent.
    truncated: bool = False
    truncation_note: str = ""
    model_backed_dispatch: Literal["DISABLED", "ENABLED"] = "DISABLED"
    merge_authorized: Literal[False] = False
    truth_boundary: str = TRUTH_BOUNDARY


@dataclass(frozen=True)
class _TaskView:
    envelope: TaskEnvelope
    checkpoint: ContinuationCheckpoint | None
    verdict: ReconciliationVerdict
    state_root: Path


def _budget_remaining(
    envelope: TaskEnvelope, checkpoint: ContinuationCheckpoint | None
) -> dict[str, float]:
    consumed = checkpoint.consumed_budget if checkpoint is not None else None
    budgets = envelope.budgets
    if consumed is None:
        return {
            "attempts": float(budgets.max_attempts),
            "launches": float(budgets.max_launches),
            "wall_seconds": float(budgets.max_wall_seconds),
            "model_calls": float(budgets.max_model_calls),
        }
    return {
        "attempts": float(max(0, budgets.max_attempts - consumed.attempts)),
        "launches": float(max(0, budgets.max_launches - consumed.launches)),
        "wall_seconds": float(
            max(0.0, budgets.max_wall_seconds - consumed.wall_seconds)
        ),
        "model_calls": float(max(0, budgets.max_model_calls - consumed.model_calls)),
    }


def _next_action(view: _TaskView) -> str:
    """The concrete next action, taken from durable state, never invented.

    Order matters: a reconciliation verdict outranks whatever the checkpoint
    said it was going to do next, because the verdict is the fresher fact and
    it is the one that knows the process is gone.
    """
    verdict = view.verdict
    if verdict.disposition is Disposition.RESUME_AT_NEXT_STEP and verdict.resume_step:
        return f"Resume task {view.envelope.task_id} at step {verdict.resume_step}."
    if verdict.disposition is Disposition.ALREADY_COMPLETE:
        return f"Nothing. Task {view.envelope.task_id} is complete; do not replay it."
    if verdict.disposition is Disposition.RECONCILE_REQUIRED:
        return (
            f"Run `atlas program reconcile` for {view.envelope.task_id} and "
            "establish what the interrupted execution actually did. Do not "
            "relaunch it."
        )
    if verdict.disposition is Disposition.HUMAN_DECISION_REQUIRED:
        return (
            f"Wait. Task {view.envelope.task_id} needs an operator decision; it "
            "is recorded in the decision queue and must not be re-asked."
        )
    if verdict.disposition is Disposition.WORKER_STILL_RUNNING:
        return f"Nothing. A worker is still running task {view.envelope.task_id}."
    if verdict.disposition is Disposition.LEASE_HELD_ELSEWHERE:
        return (
            f"Nothing. Task {view.envelope.task_id} is leased to "
            f"{view.checkpoint.identity.worker_id if view.checkpoint else 'another worker'}."
        )
    if verdict.disposition is Disposition.FAIL_CLOSED:
        return (
            f"Stop. Task {view.envelope.task_id} has unusable durable state and "
            "must not be repaired automatically."
        )
    if view.checkpoint is not None and not view.checkpoint.terminal:
        return view.checkpoint.next_action
    steps = view.envelope.checkpoint_policy.steps
    first = f" at step {steps[0]}" if steps else ""
    return f"Start task {view.envelope.task_id}{first}."


def _scan_roots(
    root: Path, queue_root: Path | None, *, governed_root: Path | None = None
) -> tuple[Path, ...]:
    """Every state root a capsule for this dispatcher must look in.

    The dispatcher publishes its heartbeat under its OWN root -- the one given
    on the command line -- while each admitted program keeps its task records
    under the state root recorded in its queue entry. Those are allowed to
    differ, and by design do whenever one dispatcher serves several programs.

    Reading only the dispatcher's root was a real defect, found by an
    independent verifier running this as an operator rather than as a test: a
    healthy, completed program produced a capsule saying "no task envelopes
    recorded under this state root", and a replacement session reading it would
    reasonably conclude there was nothing to resume. The capsule is the one
    surface a replacement session has; it must not be able to report emptiness
    that is really a lookup in the wrong place.
    """
    boundary = trusted_root(governed_root or root)
    roots: list[Path] = [checked_path(root, root=boundary)]
    if queue_root is None:
        return tuple(roots)
    try:
        queue = load_queue(queue_root, governed_root=boundary)
    except ContainmentError:
        raise
    except Exception:
        # An unreadable queue does not get to hide the dispatcher's own root.
        return tuple(roots)
    for entry in sorted(queue.entries.values(), key=lambda e: e.program_id):
        candidate = checked_path(Path(entry.state_root), root=boundary)
        if candidate not in roots:
            roots.append(candidate)
    return tuple(roots)


#: How strong a task's record is in one state root. Higher wins a tie between
#: roots. The ordering is the whole of the D-6 fix, so it is stated once here
#: rather than implied by control flow:
#:
#:   3  a TERMINAL checkpoint -- the work reached a sealed outcome
#:   2  a checkpoint that is not terminal -- the work demonstrably started
#:   1  an envelope only -- authority was recorded and nothing else happened
#:   0  unreadable -- present but unusable
#:
#: A bare envelope is the WEAKEST evidence and is what an aborted run leaves
#: behind, which is why scan order was the wrong tie-break.
_EVIDENCE_TERMINAL: Final[int] = 3
_EVIDENCE_CHECKPOINT: Final[int] = 2
_EVIDENCE_ENVELOPE_ONLY: Final[int] = 1
_EVIDENCE_UNREADABLE: Final[int] = 0


def _evidence_rank(state_root: Path, task_id: str) -> int:
    """How much this root actually knows about the task."""
    try:
        checkpoint = load_checkpoint(state_root, task_id)
    except Exception:
        return _EVIDENCE_UNREADABLE
    if checkpoint is None:
        return _EVIDENCE_ENVELOPE_ONLY
    return _EVIDENCE_TERMINAL if checkpoint.terminal else _EVIDENCE_CHECKPOINT


def _build_view(
    state_root: Path,
    envelope: TaskEnvelope,
    for_worker_id: str,
    prior_execution: tuple[str, ...],
) -> _TaskView:
    """One task's view from one root, reconciled. Never raises."""
    try:
        checkpoint = load_checkpoint(state_root, envelope.task_id)
    except Exception as exc:
        return _TaskView(
            envelope=envelope,
            checkpoint=None,
            verdict=ReconciliationVerdict(
                task_id=envelope.task_id,
                disposition=Disposition.FAIL_CLOSED,
                replay_class=envelope.replay_class,
                reason=f"durable state is unusable: {exc}",
                evidence=(type(exc).__name__,),
            ),
            state_root=state_root,
        )
    verdict = reconcile_task(
        envelope=envelope,
        checkpoint=checkpoint,
        our_worker_id=for_worker_id,
        prior_execution=prior_execution,
    )
    return _TaskView(
        envelope=envelope,
        checkpoint=checkpoint,
        verdict=verdict,
        state_root=state_root,
    )


def build_capsule(
    root: Path,
    *,
    for_worker_id: str,
    queue_root: Path | None = None,
    governed_root: Path | None = None,
) -> ContinuationCapsule:
    """Generate a capsule from durable state. Reads no conversation."""
    boundary = trusted_root(governed_root or root)
    root = checked_path(root, root=boundary)
    if queue_root is not None:
        queue_root = checked_path(queue_root, root=boundary)
    scan_roots = _scan_roots(root, queue_root, governed_root=boundary)
    views: list[_TaskView] = []
    # D-6. One task, one view -- but WHICH record wins is decided by evidence,
    # not by scan order.
    #
    # The previous rule was first-root-wins, and the dispatcher's own root is
    # scanned first. That root is exactly where debris lands: envelopes are
    # written BEFORE a program runs, so a run that aborts before any checkpoint
    # leaves an envelope with no checkpoint behind. An envelope without a
    # checkpoint reconciles to START_FRESH, launchable -- so a stale one
    # shadowed the authoritative terminal record in the program's own root and
    # the capsule told a replacement session to redo completed work.
    #
    # Not a replay: the queue entry is terminal, so the dispatcher never
    # re-runs it. The damage is to the capsule, which is the ONLY surface a
    # replacement session has.
    #
    # This defect was introduced by the fix for its own opposite. F1 was "the
    # capsule silently reports nothing because it read one root"; the repair
    # added multi-root scanning, and its tie-break became "the capsule
    # confidently reports the wrong record". Evidence strength is the rule that
    # answers both: a record carrying a terminal checkpoint outranks one
    # carrying any checkpoint, which outranks a bare envelope.
    #
    # R1 / R2. The D-6 rule chooses the strongest SURVIVING record; it cannot
    # help when the strongest survivor is a bare envelope because the terminal
    # checkpoint was LOST. That case is decided by ``reconcile_task`` itself,
    # from evidence gathered across EVERY scanned root plus the queue -- the
    # same function and the same inputs ``atlas program continuation --action
    # reconcile`` uses, so the capsule and the reconcile command cannot
    # disagree about one task. The evidence is gathered once per task.
    completed = completed_program_task_ids(queue_root, governed_root=boundary)
    evidence_cache: dict[str, tuple[str, ...]] = {}

    def prior_execution_for(task_id: str) -> tuple[str, ...]:
        if task_id not in evidence_cache:
            evidence_cache[task_id] = prior_execution_evidence(
                scan_roots, task_id, completed_elsewhere=completed, governed_root=boundary
            )
        return evidence_cache[task_id]

    seen: dict[str, int] = {}
    for scan_root in scan_roots:
        for envelope in list_envelopes(scan_root):
            if envelope.task_id in seen:
                existing = views[seen[envelope.task_id]]
                if _evidence_rank(scan_root, envelope.task_id) <= _evidence_rank(
                    existing.state_root, existing.envelope.task_id
                ):
                    continue
                # A stronger record was found in a later root. Replace the
                # weaker one and say so, rather than keeping whichever root
                # happened to be scanned first.
                views[seen[envelope.task_id]] = _build_view(
                    scan_root,
                    envelope,
                    for_worker_id,
                    prior_execution_for(envelope.task_id),
                )
                continue
            seen[envelope.task_id] = len(views)
            views.append(
                # A task whose state cannot be read still appears in the
                # capsule, as FAIL_CLOSED. Omitting it would make the capsule's
                # task list a statement that the task does not exist.
                _build_view(
                    scan_root,
                    envelope,
                    for_worker_id,
                    prior_execution_for(envelope.task_id),
                )
            )

    truncated = False
    if len(views) > _MAX_TASKS:
        truncated = True
        # Keep the tasks a reader must act on. A completed task dropped from
        # the capsule is still completed on disk and is still never replayed --
        # the no-replay guarantee lives in reconciliation, not here.
        views.sort(
            key=lambda v: (
                v.verdict.disposition is Disposition.ALREADY_COMPLETE,
                v.envelope.task_id,
            )
        )
        views = views[:_MAX_TASKS]

    tasks: list[CapsuleTask] = []
    for view in views:
        checkpoint = view.checkpoint
        artifacts = (
            tuple(f"{a.path}@{a.sha256[:12]}" for a in checkpoint.artifacts)
            if checkpoint is not None
            else ()
        )
        commands = (
            tuple(
                f"{' '.join(c.argv)[:200]} exit={c.exit_status} "
                f"started={c.started_at} ended={c.ended_at}"
                for c in checkpoint.commands
            )
            if checkpoint is not None
            else ()
        )
        capture: dict[str, dict[str, str]] = {}
        if checkpoint is not None:
            capture = {
                name: {
                    "status": item.status.value,
                    "reason": item.reason,
                    "source": item.source,
                }
                for name, item in (
                    ("commands", checkpoint.capture.commands),
                    ("artifacts", checkpoint.capture.artifacts),
                    ("changed_files", checkpoint.capture.changed_files),
                )
            }
        item_truncated = (
            len(view.verdict.evidence) > _MAX_EVIDENCE
            or len(artifacts) > _MAX_ARTIFACTS
            or len(commands) > _MAX_ARTIFACTS
        )
        truncated = truncated or item_truncated

        tasks.append(
            CapsuleTask(
                task_id=view.envelope.task_id,
                state_root=str(view.state_root),
                # Disposition, reason and launchability come from ONE verdict
                # and are not adjusted here: a capsule that overrode its own
                # reconciliation would be a second decision nobody can audit.
                disposition=view.verdict.disposition,
                replay_class=view.verdict.replay_class.value,
                reason=view.verdict.reason,
                next_action=_next_action(view),
                resume_step=view.verdict.resume_step,
                last_completed_step=(
                    checkpoint.last_completed_step if checkpoint is not None else None
                ),
                allowed_paths=view.envelope.allowed_paths,
                forbidden_paths=view.envelope.forbidden_paths,
                forbidden_actions=view.envelope.forbidden_actions,
                candidate_head=view.envelope.candidate_head,
                candidate_tree=view.envelope.candidate_tree,
                deadline_utc=view.envelope.deadline_utc,
                budget_remaining=_budget_remaining(view.envelope, checkpoint),
                blockers=checkpoint.blockers if checkpoint is not None else (),
                uncertainty=checkpoint.uncertainty if checkpoint is not None else (),
                artifacts=artifacts[:_MAX_ARTIFACTS],
                commands=commands[:_MAX_ARTIFACTS],
                execution_capture=(
                    checkpoint.execution_capture.value
                    if checkpoint is not None
                    else "NOT_CAPTURED"
                ),
                capture=capture,
                evidence=view.verdict.evidence[:_MAX_EVIDENCE],
                launchable=view.verdict.launchable,
                truncated=item_truncated,
            )
        )

    # Decisions live beside the tasks they are about, so they are gathered
    # from every scanned root for the same reason the tasks are.
    decisions_all: list[Any] = []
    for scan_root in scan_roots:
        check_children(decisions_dir(scan_root), root=boundary)
        decisions_all.extend(list_decisions(scan_root, status=DecisionStatus.OPEN))
    decisions = tuple(
        sorted(decisions_all, key=lambda d: (d.task_id, d.decision_id))
    )
    if len(decisions) > _MAX_DECISIONS:
        truncated = True
    open_decisions = tuple(
        {
            "decision_id": d.decision_id,
            "task_id": d.task_id,
            "kind": d.kind.value,
            "question": d.question,
            "requested_action": d.requested_action,
            "seen_count": d.seen_count,
            "raised_at": d.raised_at,
        }
        for d in decisions[:_MAX_DECISIONS]
    )

    beat = read_heartbeat(root)
    dispatcher: dict[str, Any] = {}
    if beat is not None:
        dispatcher = {
            "session_id": beat.dispatcher_session_id,
            "pid": beat.pid,
            "process_start_identity": beat.process_start_identity,
            "state": beat.state.value,
            "paused": beat.paused,
            "beat_at": beat.beat_at,
            "revision_head": beat.revision_head,
            "revision_tree": beat.revision_tree,
            "terminal_reason": (
                beat.terminal_reason.value if beat.terminal_reason else None
            ),
        }

    queue_view: dict[str, Any] = {}
    if queue_root is not None:
        queue = load_queue(queue_root, governed_root=boundary)
        queue_view = {
            "admitted": len(queue.entries),
            "runnable": [e.program_id for e in queue.runnable()],
            "by_status": {
                status: sorted(
                    e.program_id
                    for e in queue.entries.values()
                    if e.status.value == status
                )
                for status in sorted({e.status.value for e in queue.entries.values()})
            },
        }

    own_root = checked_path(root, root=boundary)
    elsewhere = sorted(
        {t.state_root for t in tasks if Path(t.state_root) != own_root}
    )
    split_note = ""
    if elsewhere:
        split_note = (
            "Task records for this dispatcher do not all live under its own "
            f"state root ({own_root}). They were also read from: "
            + ", ".join(elsewhere)
            + ". This is normal when one dispatcher serves programs that keep "
            "their own state; it is recorded so a reader never mistakes a "
            "lookup in the wrong root for an absence of work."
        )
    elif queue_root is None and not tasks and len(scan_roots) == 1:
        split_note = (
            "No task records under this root, and no --queue-root was given, so "
            "no other root was looked in. If an admitted program keeps its "
            "state elsewhere, re-run with --queue-root before concluding there "
            "is nothing to resume."
        )

    return ContinuationCapsule(
        state_root=str(root),
        for_worker_id=for_worker_id,
        dispatcher=dispatcher,
        queue=queue_view,
        tasks=tuple(tasks),
        state_roots_scanned=tuple(str(r) for r in scan_roots),
        root_split_note=split_note,
        open_decisions=open_decisions,
        truncated=truncated,
        truncation_note=(
            "Lists were shortened to keep the capsule bounded; the durable "
            "state under state_root is complete and authoritative."
            if truncated
            else ""
        ),
        model_backed_dispatch=(
            "ENABLED" if dispatcher.get("model_backed_dispatch") == "ENABLED" else "DISABLED"
        ),
    )


def render_capsule(capsule: ContinuationCapsule) -> str:
    """A bounded plain-text capsule. Truncation is always announced.

    The final ceiling is applied to the encoded bytes, not the character count,
    because the caller's budget is bytes and a multi-byte path would otherwise
    slip past a character-based check.
    """
    lines: list[str] = [
        "ATLAS CONTINUATION CAPSULE",
        f"generated_at: {capsule.generated_at}",
        f"state_root:   {capsule.state_root}",
        f"for_worker:   {capsule.for_worker_id}",
        "",
        "This capsule is generated from durable files. It contains no "
        "conversation history",
        "and grants nothing. Re-read the envelope on disk before any dispatch.",
        f"MODEL_BACKED_DISPATCH={capsule.model_backed_dispatch}  "
        f"MERGE_AUTHORIZED={capsule.merge_authorized}",
        "",
    ]
    if capsule.dispatcher:
        d = capsule.dispatcher
        lines += [
            "## Dispatcher",
            f"  state={d.get('state')} paused={d.get('paused')} "
            f"pid={d.get('pid')} beat_at={d.get('beat_at')}",
            f"  revision_head={d.get('revision_head') or 'UNKNOWN'}",
            f"  terminal_reason={d.get('terminal_reason') or 'none'}",
            "",
        ]
    else:
        lines += ["## Dispatcher", "  no heartbeat recorded under this state root", ""]

    if capsule.queue:
        lines += [
            "## Approved work queue",
            f"  admitted={capsule.queue.get('admitted')} "
            f"runnable={capsule.queue.get('runnable')}",
            f"  by_status={capsule.queue.get('by_status')}",
            "",
        ]

    if len(capsule.state_roots_scanned) > 1:
        lines += [
            "## State roots scanned",
            *(f"  {r}" for r in capsule.state_roots_scanned),
            "",
        ]

    lines.append("## Tasks")
    if not capsule.tasks:
        # Never a bare "nothing here". An empty task list and a lookup in the
        # wrong root read identically to a replacement session, and that
        # ambiguity already cost one verifier two runs.
        lines.append(
            f"  no task records found in {len(capsule.state_roots_scanned)} "
            f"scanned root(s): {', '.join(capsule.state_roots_scanned)}"
        )
        if capsule.root_split_note:
            lines.append(f"  NOTE: {capsule.root_split_note}")
    for task in capsule.tasks:
        lines += [
            f"  [{task.disposition.value}] {task.task_id}  "
            f"({task.replay_class}, launchable={task.launchable})",
            f"    next_action: {task.next_action}",
            f"    why:         {task.reason}",
        ]
        if task.last_completed_step or task.resume_step:
            lines.append(
                f"    steps:       last_completed={task.last_completed_step} "
                f"resume_at={task.resume_step}"
            )
        lines.append(
            f"    authority:   head={task.candidate_head[:12]} "
            f"allowed={list(task.allowed_paths)} "
            f"forbidden={list(task.forbidden_paths)}"
        )
        if len(capsule.state_roots_scanned) > 1:
            lines.append(f"    records in: {task.state_root}")
        if task.forbidden_actions:
            lines.append(f"    forbidden_actions: {list(task.forbidden_actions)}")
        lines.append(f"    budget_left: {task.budget_remaining}")
        for blocker in task.blockers:
            lines.append(f"    blocker:     {blocker}")
        for item in task.uncertainty:
            lines.append(f"    uncertain:   {item}")
        for artifact in task.artifacts:
            lines.append(f"    artifact:    {artifact}")
        for command in task.commands:
            lines.append(f"    command:     {command}")
        for name in ("commands", "artifacts", "changed_files"):
            statement = task.capture.get(name)
            if statement is None:
                continue
            # G4b, per field and separately: AVAILABLE says where the value
            # came from; UNAVAILABLE says why nobody could report it. Never
            # collapsed into one flag, because the answers differ per field.
            source = f" [{statement['source']}]" if statement.get("source") else ""
            lines.append(
                f"    capture {name + ':':<14} {statement['status']} -- "
                f"{statement['reason'][:240]}{source}"
            )
        if task.execution_capture != "OBSERVED":
            lines.append(
                "    execution:   NOT CAPTURED -- this checkpoint was written at "
                "a program boundary and observed no worker. Empty changed-file, "
                "command and artifact lists here mean nobody looked, NOT that "
                "nothing happened."
            )
        if task.truncated:
            lines.append(f"    {_TRUNCATION_MARK}: evidence/artifacts shortened")
    lines.append("")

    lines.append("## Open operator decisions (never re-asked)")
    if not capsule.open_decisions:
        lines.append("  none")
    for decision in capsule.open_decisions:
        lines += [
            f"  {decision['decision_id']} [{decision['kind']}] "
            f"task={decision['task_id']} seen={decision['seen_count']}x",
            f"    q: {decision['question']}",
            f"    a: {decision['requested_action']}",
        ]
    lines.append("")
    if capsule.root_split_note and capsule.tasks:
        lines += [f"NOTE: {capsule.root_split_note}", ""]
    if capsule.truncated:
        lines.append(f"{_TRUNCATION_MARK}: {capsule.truncation_note}")
    lines.append(f"TRUTH_BOUNDARY: {capsule.truth_boundary}")

    text = "\n".join(lines) + "\n"
    encoded = text.encode("utf-8")
    if len(encoded) <= CAPSULE_MAX_BYTES:
        return text
    notice = (
        f"\n{_TRUNCATION_MARK}: capsule exceeded {CAPSULE_MAX_BYTES} bytes and "
        "was cut here. The durable state under state_root is complete.\n"
    )
    budget = CAPSULE_MAX_BYTES - len(notice.encode("utf-8"))
    # Cut on a decoded boundary so the result is always valid UTF-8.
    cut = encoded[: max(0, budget)].decode("utf-8", errors="ignore")
    return cut + notice


def persist_capsule(root: Path, capsule: ContinuationCapsule) -> Path:
    """Write the capsule beside the dispatcher's own state, atomically."""
    return write_json_atomic(
        dispatcher_dir(root) / CAPSULE_NAME, capsule.model_dump(mode="json")
    )
