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
    list_decisions,
)
from project_atlas.orchestration.program.reconciliation import (
    Disposition,
    ReconciliationVerdict,
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
    open_decisions: tuple[dict[str, Any], ...] = ()
    #: Set when any list was shortened to fit. Never silent.
    truncated: bool = False
    truncation_note: str = ""
    model_backed_dispatch: Literal["DISABLED"] = "DISABLED"
    merge_authorized: Literal[False] = False
    truth_boundary: str = TRUTH_BOUNDARY


@dataclass(frozen=True)
class _TaskView:
    envelope: TaskEnvelope
    checkpoint: ContinuationCheckpoint | None
    verdict: ReconciliationVerdict


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


def build_capsule(
    root: Path,
    *,
    for_worker_id: str,
    queue_root: Path | None = None,
) -> ContinuationCapsule:
    """Generate a capsule from durable state. Reads no conversation."""
    views: list[_TaskView] = []
    for envelope in list_envelopes(root):
        try:
            checkpoint = load_checkpoint(root, envelope.task_id)
        except Exception as exc:
            # A task whose state cannot be read must still appear in the
            # capsule. Omitting it would make the capsule's task list a
            # statement that the task does not exist.
            views.append(
                _TaskView(
                    envelope=envelope,
                    checkpoint=None,
                    verdict=ReconciliationVerdict(
                        task_id=envelope.task_id,
                        disposition=Disposition.FAIL_CLOSED,
                        replay_class=envelope.replay_class,
                        reason=f"durable state is unusable: {exc}",
                        evidence=(type(exc).__name__,),
                    ),
                )
            )
            continue
        verdict = reconcile_task(
            envelope=envelope, checkpoint=checkpoint, our_worker_id=for_worker_id
        )
        views.append(
            _TaskView(envelope=envelope, checkpoint=checkpoint, verdict=verdict)
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
        item_truncated = (
            len(view.verdict.evidence) > _MAX_EVIDENCE or len(artifacts) > _MAX_ARTIFACTS
        )
        truncated = truncated or item_truncated
        tasks.append(
            CapsuleTask(
                task_id=view.envelope.task_id,
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
                evidence=view.verdict.evidence[:_MAX_EVIDENCE],
                launchable=view.verdict.launchable,
                truncated=item_truncated,
            )
        )

    decisions = list_decisions(root, status=DecisionStatus.OPEN)
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
        queue = load_queue(queue_root)
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

    return ContinuationCapsule(
        state_root=str(root),
        for_worker_id=for_worker_id,
        dispatcher=dispatcher,
        queue=queue_view,
        tasks=tuple(tasks),
        open_decisions=open_decisions,
        truncated=truncated,
        truncation_note=(
            "Lists were shortened to keep the capsule bounded; the durable "
            "state under state_root is complete and authoritative."
            if truncated
            else ""
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

    lines.append("## Tasks")
    if not capsule.tasks:
        lines.append("  no task envelopes recorded under this state root")
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
        if task.forbidden_actions:
            lines.append(f"    forbidden_actions: {list(task.forbidden_actions)}")
        lines.append(f"    budget_left: {task.budget_remaining}")
        for blocker in task.blockers:
            lines.append(f"    blocker:     {blocker}")
        for item in task.uncertainty:
            lines.append(f"    uncertain:   {item}")
        for artifact in task.artifacts:
            lines.append(f"    artifact:    {artifact}")
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
