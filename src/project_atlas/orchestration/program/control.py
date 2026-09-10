"""The read-only control contract Atlas Studio consumes.

Studio observes; it does not drive. Everything here is either a projection of
durable state or a *request* routed through the same governance a command-line
operator goes through. There is no write path from a UI into program state.

  UI != CANONICAL TRUTH
  OBSERVATION != CONTROL
  REQUEST != AUTHORIZATION

`CONTRACT_VERSION` is what makes this stable to consume. Fields are added, not
renamed or repurposed; a consumer that does not recognise a field ignores it,
and a consumer pinned to an older version keeps working. If a field's meaning
would have to change, a new field appears beside it and the old one is
deprecated in place.

CLOSING STUDIO MUST NOT STOP WORK. It cannot: the supervisor is a separate
process, its state is on disk, and every function in this module reads. There
is a test that asserts reading the view leaves the state file byte-identical.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from project_atlas.orchestration.autonomy.lease_projection import (
    active_rows,
    load_projection,
)
from project_atlas.orchestration.program import service
from project_atlas.orchestration.program.enrollment import load_registry
from project_atlas.orchestration.program.loader import LoadedProgram
from project_atlas.orchestration.program.models import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    AttemptPhase,
    ExecutionConfidence,
    ProgramError,
)
from project_atlas.orchestration.program.store import (
    ProgramStateRecord,
    append_event,
    load_state,
    persist_state,
    read_events,
    state_dir,
)
from project_atlas.orchestration.program.supervisor import (
    DONE_STATES,
    IN_FLIGHT_STATES,
    ProgramSupervisor,
)

CONTRACT_ID: Final[str] = "atlas.program.control"
CONTRACT_VERSION: Final[int] = 1

#: What a consumer may ask for. Each is a request routed through existing
#: governance, never a direct mutation, and none of them can grant anything.
SUPPORTED_ACTIONS: Final[tuple[str, ...]] = (
    "pause",
    "resume",
    "cancel",
    "reconcile",
)

#: Named here so a UI can render honestly rather than implying it could.
UNSUPPORTED_ACTIONS: Final[dict[str, str]] = {
    "grant_owner_gate": (
        "no interface can grant an owner gate. It is granted outside this "
        "system or not at all"
    ),
    "raise_limits": (
        "limits come from the approved program file. Changing them is a new "
        "approval, not a control action"
    ),
    "merge": "this package never merges",
    "adopt_running_process": (
        "a session enters a program only through an explicit handoff of a "
        "STORED session; no live process is ever adopted"
    ),
    "edit_task": (
        "the approved program is immutable while it runs; editing it is "
        "detected as PROGRAM_DIGEST_DRIFT and refused"
    ),
}


class ControlError(ProgramError):
    code = "PROGRAM_CONTROL_ERROR"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def control_view(
    root: Path, loaded: LoadedProgram, *, event_limit: int = 25
) -> dict[str, Any]:
    """The whole picture, read-only, in one versioned object."""
    supervisor = ProgramSupervisor(loaded, state_root=root)
    state = load_state(root)
    identity = service.read_identity(root)
    program = loaded.program

    tasks: list[dict[str, Any]] = []
    for task in program.tasks:
        record = state.tasks.get(task.task_id) if state is not None else None
        profile = loaded.effective_profile(task.task_id)
        attempt = (
            state.attempts.get(record.last_attempt_id)
            if state is not None and record is not None and record.last_attempt_id
            else None
        )
        tasks.append(
            {
                "task_id": task.task_id,
                "title": task.title,
                "depends_on": list(task.depends_on),
                "state": record.state.value if record else "DISCOVERED",
                "is_running": bool(record and record.state in IN_FLIGHT_STATES),
                "is_done": bool(record and record.state in DONE_STATES),
                "agent_id": profile.agent_id,
                "adapter": profile.adapter.value,
                "attempts": record.attempts if record else 0,
                "launches": record.launches if record else 0,
                "last_failure_class": (
                    record.last_failure_class.value
                    if record and record.last_failure_class
                    else None
                ),
                "awaiting_independent_verification": bool(
                    record and record.awaiting_independent_verification
                ),
                "verified_by_agent_id": record.verified_by_agent_id if record else None,
                "owner_gate": task.owner_gate.value if task.owner_gate else None,
                "waiting_on": record.pending_observer_id if record else None,
                "last_attempt": (
                    {
                        "attempt_id": attempt.attempt_id,
                        "phase": attempt.phase.value,
                        "confidence": (
                            attempt.confidence.value if attempt.confidence else None
                        ),
                        "acceptance_passed": attempt.acceptance_passed,
                        "runtime_session_id": attempt.runtime_session_id,
                        "policy_denials": attempt.policy_denials,
                        "started_at": attempt.started_at,
                        "ended_at": attempt.ended_at,
                    }
                    if attempt is not None
                    else None
                ),
                "acceptance": [
                    {"check_id": check.check_id, "kind": check.kind.value,
                     "description": check.description}
                    for check in task.acceptance
                ],
            }
        )

    ownership: list[dict[str, Any]] = []
    try:
        for row in active_rows(load_projection(state_dir(root))):
            ownership.append(
                {
                    "task_id": row.package_id,
                    "agent_id": row.agent_id,
                    "lease_id": row.lease_id,
                    "authorized_paths": list(row.authorized_paths),
                }
            )
    except ProgramError:
        ownership = []

    needs_reconcile = (
        [
            {
                "attempt_id": attempt.attempt_id,
                "task_id": attempt.task_id,
                "phase": attempt.phase.value,
            }
            for attempt in state.attempts.values()
            if attempt.confidence is ExecutionConfidence.UNCERTAIN
            and attempt.phase is not AttemptPhase.TERMINAL
        ]
        if state is not None
        else []
    )

    limits = program.limits
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "package_id": PACKAGE_ID,
        "generated_at": _utc_now(),
        "truth_boundary": TRUTH_BOUNDARY,
        "read_only": True,
        "program": {
            "program_id": program.program_id,
            "objective": program.objective,
            "approved_by": program.approved_by,
            "approval_reference": program.approval_reference,
            "program_sha256": loaded.digest,
            "base_pin": program.base_pin,
            "workspace": str(loaded.workspace),
            "complete": bool(state.complete) if state else False,
            "paused": bool(state.paused) if state else False,
            "paused_by": state.paused_by if state else None,
            "cancel_requested": bool(state.cancel_requested) if state else False,
            "last_stop_reason": (
                state.last_stop_reason.value
                if state is not None and state.last_stop_reason
                else None
            ),
        },
        "supervisor": {
            "service": identity.to_public_dict() if identity else None,
            "service_alive": service.service_is_alive(identity),
            "note": (
                "the supervisor is a separate process. Closing a viewer does "
                "not stop it, and nothing in this contract can"
            ),
        },
        "tasks": tasks,
        "ownership": ownership,
        "needs_reconciliation": needs_reconcile,
        "status": supervisor.status(),
        "limits": {
            "declared": limits.model_dump(mode="json"),
            "launches_used": state.total_launches if state else 0,
            "launches_remaining": (
                max(0, limits.max_task_launches - state.total_launches)
                if state
                else limits.max_task_launches
            ),
            "estimated_cost_usd": state.estimated_cost_usd if state else 0.0,
            "estimated_cost_note": (
                "client-side estimate reported by the runtime; not billed "
                "spend, and 0.0 can mean the runtime reports no cost at all"
            ),
        },
        "actions": {
            "supported": list(SUPPORTED_ACTIONS),
            "unsupported": dict(UNSUPPORTED_ACTIONS),
            "note": (
                "every supported action is a REQUEST routed through the same "
                "governance a command-line operator goes through. None of them "
                "grants anything"
            ),
        },
        "recent_events": read_events(root, limit=event_limit),
        "agents": _agent_rows(root),
        "merge_authorized": False,
        "execution_authorized": False,
    }


def _agent_rows(root: Path) -> list[dict[str, Any]]:
    try:
        registry = load_registry(root)
    except ProgramError:
        return []
    return [
        {
            "agent_id": agent.agent_id,
            "role": agent.role,
            "adapter": agent.adapter.value,
            "status": agent.status.value,
            "workspace_root": agent.workspace_root,
            "assigned_program": agent.assigned_program,
            "runtime_substitution_authorized": agent.runtime_substitution_authorized,
        }
        for agent in sorted(registry.agents.values(), key=lambda item: item.agent_id)
    ]


def _require_state(root: Path) -> ProgramStateRecord:
    state = load_state(root)
    if state is None:
        raise ControlError(
            "this program has never been started", code="NO_STATE"
        )
    return state


def pause(root: Path, *, requested_by: str) -> dict[str, Any]:
    """Stop starting new work. Workers already running are left alone.

    Reversible, and deliberately gentler than cancellation: interrupting a
    running worker turns a reversible operator decision into a set of uncertain
    outcomes that need reconciling, which is not what anyone means by "pause".
    """
    state = _require_state(root)
    state.paused = True
    state.paused_by = requested_by
    state.paused_at = _utc_now()
    persist_state(root, state)
    append_event(root, "PROGRAM_PAUSED", {"requested_by": requested_by})
    return {
        "program_id": state.program_id,
        "paused": True,
        "paused_by": requested_by,
        "effect": (
            "no further worker is started. Any worker already running is "
            "allowed to finish, so nothing becomes UNCERTAIN because of this"
        ),
        "reversible": True,
        "merge_authorized": False,
    }


def resume(root: Path, *, requested_by: str) -> dict[str, Any]:
    """Clear a pause. Does not clear a cancellation, which is not reversible."""
    state = _require_state(root)
    if state.cancel_requested:
        raise ControlError(
            "this program was cancelled, not paused. Cancellation is not "
            "reversible from here: start it again if that is what you mean",
            code="CANNOT_RESUME_CANCELLED",
        )
    state.paused = False
    state.paused_by = None
    state.paused_at = None
    persist_state(root, state)
    append_event(root, "PROGRAM_RESUMED", {"requested_by": requested_by})
    return {
        "program_id": state.program_id,
        "paused": False,
        "resumed_by": requested_by,
        "effect": (
            "the supervisor selects eligible work again on its next cycle. A "
            "running service picks this up without being restarted"
        ),
        "merge_authorized": False,
    }


def request_action(
    root: Path,
    loaded: LoadedProgram,
    *,
    action: str,
    requested_by: str,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    """The single entry point a UI uses. Everything else here is a read.

    Deliberately narrow. A consumer cannot reach `enroll`, `assign`, `handoff`
    or anything that changes what a program may do -- those are operator acts
    with their own recorded provenance, not things a viewer should be able to
    trigger.
    """
    if action not in SUPPORTED_ACTIONS:
        reason = UNSUPPORTED_ACTIONS.get(action)
        raise ControlError(
            reason or f"unsupported action {action!r}",
            code="ACTION_NOT_SUPPORTED",
        )
    if action == "pause":
        return pause(root, requested_by=requested_by)
    if action == "resume":
        return resume(root, requested_by=requested_by)

    supervisor = ProgramSupervisor(loaded, state_root=root)
    if action == "cancel":
        report = supervisor.request_cancel()
        append_event(root, "CANCEL_REQUESTED_VIA_CONTROL", {"requested_by": requested_by})
        return {**report, "requested_by": requested_by}
    # reconcile
    report = supervisor.reconcile(resolve_uncertain=attempt_id)
    if attempt_id is not None:
        append_event(
            root,
            "RECONCILED_VIA_CONTROL",
            {"requested_by": requested_by, "attempt_id": attempt_id},
        )
    return {**report, "requested_by": requested_by}
