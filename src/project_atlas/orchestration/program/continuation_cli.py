"""Operator commands for the durable continuation layer.

Every command here is read-only or writes only durable bookkeeping the operator
explicitly asked for. None of them merges, pushes, installs a service, changes
an account, or enables model-backed dispatch. Two of them deliberately *print a
command instead of running it* -- ``dispatcher --action restart`` and
``continuation --action rollback`` -- because restarting a service and rolling
back a deployment are acts on a system this process was not authorized to
change, and emitting the exact command an operator can check is the honest
version of "support that operation".

Output is one JSON object per invocation, through the same ``emit`` contract the
rest of this CLI uses, so a script never has to parse prose.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from project_atlas.orchestration.program.approved_queue import (
    admit,
    load_queue,
    verify_entry,
    withdraw,
)
from project_atlas.orchestration.program.capsule import (
    build_capsule,
    persist_capsule,
    render_capsule,
)
from project_atlas.orchestration.program.continuation import (
    TRUTH_BOUNDARY,
    ContinuationError,
    list_checkpoints,
    list_envelopes,
    load_checkpoint,
    load_envelope,
)
from project_atlas.orchestration.program.decisions import (
    DecisionStatus,
    list_decisions,
    record_answer,
    withdraw_decision,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.reconciliation import reconcile_root
from project_atlas.orchestration.program.resident import (
    DispatcherState,
    ResidentDispatcher,
    clear_pause,
    dispatcher_status,
    request_drain,
    request_pause,
    request_stop,
    request_wake,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def _root(args: argparse.Namespace) -> Path:
    root = getattr(args, "state_root", None)
    if root is None:
        raise ContinuationError(
            "--state-root is required for continuation commands",
            code="STATE_ROOT_REQUIRED",
        )
    return Path(root).expanduser().resolve()


def _queue_root(args: argparse.Namespace) -> Path:
    queue_root = getattr(args, "queue_root", None)
    if queue_root is None:
        raise ContinuationError(
            "--queue-root is required: the dispatcher takes work from an "
            "operator-admitted queue and from nowhere else",
            code="QUEUE_ROOT_REQUIRED",
        )
    return Path(queue_root).expanduser().resolve()


# ------------------------------------------------------------------- queue


def cmd_queue(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    queue_root = _queue_root(args)
    action = args.action
    if action == "list":
        queue = load_queue(queue_root)
        rows = []
        for entry in sorted(queue.entries.values(), key=lambda e: e.program_id):
            try:
                verify_entry(entry)
                pin = "MATCHES_ADMITTED_BYTES"
            except ContinuationError as exc:
                pin = f"REFUSED: {getattr(exc, 'code', 'QUEUE_ERROR')}"
            rows.append({**entry.model_dump(mode="json"), "pin_check": pin})
        return {
            "queue_root": str(queue_root),
            "entries": rows,
            "runnable": [e.program_id for e in queue.runnable()],
            "truth_boundary": TRUTH_BOUNDARY,
        }, EXIT_OK
    if action == "admit":
        if not (args.admitted_by and args.reference and args.program):
            return {
                "error": "admit requires --program, --admitted-by and --reference",
                "code": "ADMIT_ARGS_MISSING",
            }, EXIT_USAGE
        program_path = Path(args.program).expanduser().resolve()
        loaded = load_program(program_path)
        state_root = (
            Path(args.state_root).expanduser().resolve()
            if getattr(args, "state_root", None)
            else program_path.parent
        )
        entry = admit(
            queue_root,
            program_path=program_path,
            program_id=loaded.program.program_id,
            state_root=state_root,
            admitted_by=args.admitted_by,
            reference=args.reference,
            note=args.note or "",
        )
        # A sleeping dispatcher should see this without waiting a full tick.
        request_wake(state_root, reason=f"admitted {entry.program_id}")
        return {
            "admitted": entry.model_dump(mode="json"),
            "wake_requested": True,
            "note": (
                "Admission records a pin on the program file's bytes. Changing "
                "the file after admission makes the entry refuse to run until "
                "it is re-admitted."
            ),
            "merge_authorized": False,
        }, EXIT_OK
    if action == "withdraw":
        if not args.program_id:
            return {
                "error": "withdraw requires --program-id",
                "code": "WITHDRAW_ARGS_MISSING",
            }, EXIT_USAGE
        entry = withdraw(queue_root, args.program_id, note=args.note or "")
        return {"withdrawn": entry.model_dump(mode="json")}, EXIT_OK
    return {"error": f"unknown queue action {action}"}, EXIT_USAGE


# -------------------------------------------------------------- dispatcher


def cmd_dispatcher(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    action = args.action
    if action == "status":
        return dispatcher_status(root), EXIT_OK
    if action == "pause":
        request_pause(root, requested_by=args.requested_by or "operator")
        return {
            "paused": True,
            "note": (
                "New program dispatch is withheld. A program already running "
                "is left to finish; pause is not cancel."
            ),
        }, EXIT_OK
    if action == "resume":
        cleared = clear_pause(root)
        return {"paused": False, "pause_record_cleared": cleared}, EXIT_OK
    if action == "stop":
        request_stop(root, requested_by=args.requested_by or "operator")
        return {
            "stop_requested": True,
            "note": "Honoured at the next tick boundary; a running program is "
            "not interrupted.",
        }, EXIT_OK
    if action == "drain":
        request_drain(root, requested_by=args.requested_by or "operator")
        return {
            "drain_requested": True,
            "note": "The current program finishes, nothing new starts, then the "
            "dispatcher exits.",
        }, EXIT_OK
    if action == "wake":
        request_wake(root, reason=args.requested_by or "operator")
        return {"wake_requested": True}, EXIT_OK
    if action == "restart":
        # Deliberately not performed. Restarting a resident process is an act on
        # a system this command was not authorized to change, and a command
        # that printed "restarted" without having the privileges to do it would
        # be the kind of claim this package exists to refuse.
        return {
            "performed": False,
            "reason": "NOT_AUTHORIZED_FROM_HERE",
            "operator_commands": [
                f"atlas program dispatcher --state-root {root} --action drain",
                "# wait for terminal_reason=OPERATOR_DRAIN in the heartbeat, then:",
                f"atlas program dispatcher --state-root {root} "
                f"--queue-root <QUEUE_ROOT> --action run",
            ],
            "note": (
                "No service is installed by this package. If one is installed "
                "later, the operator restarts it through the service manager, "
                "not through this command."
            ),
        }, EXIT_OK
    if action == "run":
        queue_root = _queue_root(args)
        dispatcher = ResidentDispatcher(
            root=root,
            queue_root=queue_root,
            checkout=Path(args.checkout).expanduser().resolve()
            if getattr(args, "checkout", None)
            else None,
            registry_root=Path(args.registry).expanduser().resolve()
            if getattr(args, "registry", None)
            else None,
            tick_seconds=float(args.tick_seconds),
        )
        reason = dispatcher.run(
            max_ticks=args.max_ticks,
            max_seconds=args.max_seconds,
            exit_when_drained=bool(args.exit_when_drained),
        )
        status = dispatcher_status(root)
        queue_status = str(status.get("queue_status") or "UNKNOWN")
        payload: dict[str, Any] = {
            "terminal_reason": reason.value,
            "ticks": dispatcher._ticks,
            "programs_started": dispatcher._programs_started,
            "launches": dispatcher._launches,
            # READABLE / UNREADABLE / UNKNOWN. Surfaced at the TOP level, not
            # only inside the heartbeat, because zero launches means something
            # different under each and an operator reading this output was
            # previously unable to tell them apart.
            "queue_status": queue_status,
            "queue_error": status.get("queue_error"),
            "queue_error_code": status.get("queue_error_code"),
            "notes": dispatcher._last_notes,
            "model_calls": 0,
            "model_backed_dispatch": "DISABLED",
            "status": status,
        }
        if queue_status == "UNREADABLE":
            # A refusal, in the same shape every other refusal in this CLI uses,
            # so a script branching on `code` sees it without special-casing.
            payload["code"] = str(status.get("queue_error_code") or "QUEUE_UNREADABLE")
            payload["error"] = (
                "the approved-work queue could not be read, so nothing was "
                f"dispatched: {status.get('queue_error')}"
            )
            return payload, EXIT_ERROR
        return payload, EXIT_OK
    return {"error": f"unknown dispatcher action {action}"}, EXIT_USAGE


# ----------------------------------------------------------------- capsule


def cmd_capsule(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    queue_root = (
        Path(args.queue_root).expanduser().resolve()
        if getattr(args, "queue_root", None)
        else None
    )
    capsule = build_capsule(
        root, for_worker_id=args.worker_id or "unassigned", queue_root=queue_root
    )
    written = persist_capsule(root, capsule)
    rendered = render_capsule(capsule)
    return {
        "capsule_path": str(written),
        "capsule": capsule.model_dump(mode="json"),
        "rendered": rendered,
        "rendered_bytes": len(rendered.encode("utf-8")),
        "note": (
            "Generated from durable files only. It contains no conversation "
            "history and grants nothing; re-read the envelope before dispatch."
        ),
    }, EXIT_OK


# ---------------------------------------------------------------- envelopes


def cmd_envelope(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    if args.action == "list":
        return {
            "state_root": str(root),
            "envelopes": [e.model_dump(mode="json") for e in list_envelopes(root)],
        }, EXIT_OK
    if args.action == "show":
        if not args.task:
            return {"error": "show requires --task", "code": "TASK_REQUIRED"}, EXIT_USAGE
        envelope = load_envelope(root, args.task)
        if envelope is None:
            return {
                "error": f"no envelope recorded for {args.task}",
                "code": "ENVELOPE_MISSING",
            }, EXIT_ERROR
        return {
            "envelope": envelope.model_dump(mode="json"),
            "digest": envelope.digest(),
        }, EXIT_OK
    return {"error": f"unknown envelope action {args.action}"}, EXIT_USAGE


def cmd_checkpoint(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    if args.action == "list":
        return {
            "state_root": str(root),
            "checkpoints": [
                c.model_dump(mode="json") for c in list_checkpoints(root)
            ],
        }, EXIT_OK
    if args.action == "show":
        if not args.task:
            return {"error": "show requires --task", "code": "TASK_REQUIRED"}, EXIT_USAGE
        checkpoint = load_checkpoint(root, args.task)
        if checkpoint is None:
            return {
                "checkpoint": None,
                "note": f"no checkpoint has ever been written for {args.task}",
            }, EXIT_OK
        return {"checkpoint": checkpoint.model_dump(mode="json")}, EXIT_OK
    return {"error": f"unknown checkpoint action {args.action}"}, EXIT_USAGE


# ----------------------------------------------------------- reconciliation


def cmd_continuation(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    if args.action == "reconcile":
        verdicts = reconcile_root(root, our_worker_id=args.worker_id or "unassigned")
        return {
            "state_root": str(root),
            "verdicts": [
                {
                    "task_id": v.task_id,
                    "disposition": v.disposition.value,
                    "replay_class": v.replay_class.value,
                    "reason": v.reason,
                    "resume_step": v.resume_step,
                    "launchable": v.launchable,
                    "evidence": list(v.evidence),
                }
                for v in verdicts
            ],
            "completed_replay_count": 0,
            "note": (
                "A disposition is not a dispatch. Authority is rechecked "
                "immediately before any launch."
            ),
        }, EXIT_OK
    if args.action == "rollback":
        # Printed, never performed. See the module docstring.
        return {
            "performed": False,
            "reason": "NOT_AUTHORIZED_FROM_HERE",
            "operator_procedure": [
                "1. Withhold new work:  atlas program dispatcher "
                f"--state-root {root} --action pause",
                "2. Let in-flight work finish: watch `--action status` until "
                "state is not RUNNING_PROGRAM.",
                "3. Stop the dispatcher: `--action drain`, then confirm "
                "terminal_reason=OPERATOR_DRAIN.",
                "4. Repoint the pinned checkout at the previous revision "
                "(git -C <CHECKOUT> checkout <PREVIOUS_HEAD>) and reinstall "
                "the package non-editable into the pinned environment.",
                "5. Durable state is forward-compatible by construction: this "
                "layer only ADDS files under the program state directory "
                "(envelopes/, checkpoints/, decisions/, dispatcher/). A "
                "previous revision ignores them; nothing has to be deleted "
                "and nothing is migrated in place.",
                "6. Restart the dispatcher and confirm revision_head in the "
                "heartbeat is the rolled-back revision.",
            ],
            "state_compatibility": "ADDITIVE_ONLY_NO_IN_PLACE_MIGRATION",
            "note": (
                "Rollback repoints code. It never deletes checkpoints: a "
                "deleted checkpoint is how completed work becomes replayable."
            ),
        }, EXIT_OK
    return {"error": f"unknown continuation action {args.action}"}, EXIT_USAGE


# --------------------------------------------------------------- decisions


def cmd_decisions(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    if args.action == "list":
        status = DecisionStatus(args.status) if args.status else None
        rows = list_decisions(root, status=status)
        return {
            "state_root": str(root),
            "decisions": [r.model_dump(mode="json") for r in rows],
            "open_count": len(list_decisions(root, status=DecisionStatus.OPEN)),
            "note": (
                "Each blocker is recorded once. A recurrence bumps seen_count; "
                "it never creates a second request and never re-notifies."
            ),
        }, EXIT_OK
    if args.action == "answer":
        if not (args.decision_id and args.answered_by and args.answer):
            return {
                "error": "answer requires --decision-id, --answered-by and --answer",
                "code": "ANSWER_ARGS_MISSING",
            }, EXIT_USAGE
        request = record_answer(
            root,
            args.decision_id,
            answered_by=args.answered_by,
            answer=args.answer,
        )
        return {
            "decision": request.model_dump(mode="json"),
            "note": (
                "Recording an answer is an evidence act. It unblocks selection; "
                "it does not widen what the task may do. Owner gates are "
                "unchanged."
            ),
            "merge_authorized": False,
        }, EXIT_OK
    if args.action == "withdraw":
        if not (args.decision_id and args.answer):
            return {
                "error": "withdraw requires --decision-id and --answer (the reason)",
                "code": "WITHDRAW_ARGS_MISSING",
            }, EXIT_USAGE
        request = withdraw_decision(root, args.decision_id, reason=args.answer)
        return {"decision": request.model_dump(mode="json")}, EXIT_OK
    return {"error": f"unknown decisions action {args.action}"}, EXIT_USAGE


CONTINUATION_HANDLERS: dict[
    str, Any
] = {
    "queue": cmd_queue,
    "dispatcher": cmd_dispatcher,
    "capsule": cmd_capsule,
    "envelope": cmd_envelope,
    "checkpoint": cmd_checkpoint,
    "continuation": cmd_continuation,
    "decisions": cmd_decisions,
}


def register_continuation_commands(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Attach the durable continuation commands to the ``program`` subparser."""
    specs: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        (
            "queue",
            "Inspect or change the operator-approved work queue. The dispatcher "
            "takes work from here and from nowhere else.",
            ("list", "admit", "withdraw"),
        ),
        (
            "dispatcher",
            "Run or control the resident model-free dispatcher.",
            ("status", "run", "pause", "resume", "stop", "drain", "wake", "restart"),
        ),
        (
            "capsule",
            "Generate the bounded continuation capsule a replacement session "
            "resumes from. Reads durable files only.",
            (),
        ),
        ("envelope", "Inspect durable task envelopes.", ("list", "show")),
        ("checkpoint", "Inspect durable continuation checkpoints.", ("list", "show")),
        (
            "continuation",
            "Restart reconciliation over durable checkpoints, or the exact "
            "operator rollback procedure.",
            ("reconcile", "rollback"),
        ),
        (
            "decisions",
            "The durable operator decision queue. Asked once, never re-asked.",
            ("list", "answer", "withdraw"),
        ),
    )
    for name, help_text, actions in specs:
        child = sub.add_parser(name, help=help_text)
        child.add_argument(
            "--state-root",
            type=Path,
            default=None,
            help="Directory holding program state. Never inside the workspace.",
        )
        if actions:
            child.add_argument(
                "--action",
                required=True,
                choices=actions,
                help="Which operation to perform.",
            )
        child.add_argument("--queue-root", type=Path, default=None)
        child.add_argument("--program", type=Path, default=None)
        child.add_argument("--program-id", default=None)
        child.add_argument("--task", default=None)
        child.add_argument("--worker-id", default=None)
        child.add_argument("--admitted-by", default=None)
        child.add_argument("--reference", default=None)
        child.add_argument("--requested-by", default=None)
        child.add_argument("--note", default=None)
        child.add_argument("--decision-id", default=None)
        child.add_argument("--answered-by", default=None)
        child.add_argument("--answer", default=None)
        child.add_argument(
            "--status", default=None, choices=[s.value for s in DecisionStatus]
        )
        child.add_argument("--checkout", type=Path, default=None)
        child.add_argument("--registry", type=Path, default=None)
        child.add_argument("--tick-seconds", type=float, default=5.0)
        child.add_argument("--max-ticks", type=int, default=None)
        child.add_argument("--max-seconds", type=float, default=None)
        child.add_argument("--exit-when-drained", action="store_true")


__all__ = [
    "CONTINUATION_HANDLERS",
    "DispatcherState",
    "register_continuation_commands",
]
