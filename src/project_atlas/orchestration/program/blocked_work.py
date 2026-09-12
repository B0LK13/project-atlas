"""What happens when a task blocks: once, in writing, then different work.

The three acts the governing directive requires, in this order and no other:

1. **Persist one blocker/decision record.** One. A recurrence bumps a counter;
   it does not create a second request and does not re-notify.
2. **Release its lease safely.** Safely means through the existing projection,
   with the same foreign-worker and stale-base checks any other release gets --
   a blocked task does not get a privileged path to drop a lease it might not
   own.
3. **Select another eligible authorized fallback.** From the envelope's own
   ``fallback_task_ids``, which came from the approved program. Never from a
   scan, a backlog guess, or anything invented to fill the gap.

And the fourth act, which is a refusal: **do not ask again.** No repeated
polling of the blocker, no restating it in a later cycle, no "checking whether
it cleared". An open decision is a durable fact and the work moves on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from project_atlas.orchestration.autonomy.lease_projection import (
    ProjectionError,
    active_rows,
    load_projection,
    project_release,
)
from project_atlas.orchestration.autonomy.models import AgentCapability, AgentLease
from project_atlas.orchestration.program.continuation import (
    TaskEnvelope,
    list_envelopes,
)
from project_atlas.orchestration.program.decisions import (
    DecisionKind,
    DecisionRequest,
    blocked_task_ids,
    raise_decision,
)


@dataclass(frozen=True)
class BlockOutcome:
    """What the three acts actually did. Every field is an observation."""

    decision: DecisionRequest
    #: False for a recurrence. Callers use it to decide whether to notify, and
    #: it is the single boolean that separates a decision queue an operator
    #: reads from one they learn to ignore.
    newly_raised: bool
    lease_released: bool
    lease_release_detail: str
    #: The fallback that may run instead, or None when nothing else is
    #: eligible. None is a legitimate answer: inventing work would not be.
    fallback_task_id: str | None
    fallback_reason: str


def _release_lease_for(root: Path, *, task_id: str) -> tuple[bool, str]:
    """Release the ACTIVE projected lease for one task, or say why not.

    The lease is reconstructed from the projected row rather than accepted from
    a caller. A caller that could supply the lease could supply somebody
    else's, and ``project_release`` would then be asked to release a lease on
    behalf of a worker that does not hold it -- which it would refuse, but
    refusing a malformed request is worse than never being able to make one.
    """
    try:
        projection = load_projection(root)
    except ProjectionError as exc:
        return False, f"lease projection is unusable: {exc}"
    rows = [row for row in active_rows(projection) if row.package_id == task_id]
    if not rows:
        return False, f"no ACTIVE projected lease for {task_id}"
    row = rows[0]
    capabilities: list[AgentCapability] = []
    for name in row.capabilities:
        try:
            capabilities.append(AgentCapability(name))
        except ValueError:
            continue
    if not capabilities:
        capabilities = [AgentCapability.IMPLEMENT]
    lease = AgentLease(
        lease_id=row.lease_id,
        agent_id=row.agent_id,
        package_id=row.package_id,
        branch=row.branch,
        worktree=row.worktree,
        base_pin=row.base_pin,
        authorized_paths=row.authorized_paths,
        forbidden_paths=row.forbidden_paths,
        capabilities=tuple(capabilities),
        start_state=row.start_state,
        expected_output="blocked: released to an operator decision",
        expiry_or_terminal_condition="BLOCKED_PENDING_OPERATOR_DECISION",
        active=True,
        sequence=1,
    )
    try:
        project_release(root, lease, live_main=row.base_pin)
    except ProjectionError as exc:
        return False, f"release refused by the projection: {exc}"
    return True, f"released lease {row.lease_id} held by {row.agent_id}"


def select_fallback(
    root: Path, envelope: TaskEnvelope, *, exclude: frozenset[str] = frozenset()
) -> tuple[str | None, str]:
    """The first eligible fallback from the approved program, or nothing.

    Eligibility here is narrow and deliberately so: the fallback must be named
    in this envelope (so it came from the approved program), must itself have a
    durable envelope (so its authority is recorded), and must not have an open
    operator decision of its own (so yielding to it does not immediately
    produce a second question).
    """
    if not envelope.fallback_task_ids:
        return None, "the envelope declares no fallback tasks"
    blocked = blocked_task_ids(root) | exclude | {envelope.task_id}
    known = {item.task_id for item in list_envelopes(root)}
    for candidate in envelope.fallback_task_ids:
        if candidate in blocked:
            continue
        if candidate not in known:
            continue
        return candidate, f"{candidate} is approved, enveloped and unblocked"
    return (
        None,
        "every declared fallback is itself blocked or has no recorded envelope",
    )


def handle_blocked_task(
    root: Path,
    *,
    envelope: TaskEnvelope,
    kind: DecisionKind,
    subject: str,
    question: str,
    requested_action: str,
    worker_id: str,
    session_id: str,
    evidence: tuple[str, ...] = (),
) -> BlockOutcome:
    """Perform the three acts, in order, and report each one."""
    decision, newly = raise_decision(
        root,
        program_id=envelope.program_id,
        task_id=envelope.task_id,
        kind=kind,
        subject=subject,
        question=question,
        requested_action=requested_action,
        worker_id=worker_id,
        session_id=session_id,
        evidence=evidence,
    )
    released, detail = _release_lease_for(root, task_id=envelope.task_id)
    fallback, reason = select_fallback(root, envelope)
    return BlockOutcome(
        decision=decision,
        newly_raised=newly,
        lease_released=released,
        lease_release_detail=detail,
        fallback_task_id=fallback,
        fallback_reason=reason,
    )
