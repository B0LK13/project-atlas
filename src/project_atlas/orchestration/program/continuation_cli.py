"""Operator commands for the durable continuation layer.

Every command here is read-only or writes only durable bookkeeping the operator
explicitly asked for. None of them merges, pushes, installs a service, changes
an account, or enables model-backed dispatch.

``continuation --action rollback`` deliberately *prints a procedure instead of
running it*: rolling back moves a pinned revision, an operator decision with a
blast radius this process has no authority over.

``dispatcher --action restart`` (ATLAS-OPERATOR-RECOVERY-FOLLOWUP-001) takes a
witness before anything stops, then either prints the operator commands
(``--mode delegate``, the default) or -- only when the operator has declared a
``restart_command`` under the state root -- drains the dispatcher through the
existing ``request_drain`` and starts exactly that command (``--mode
supervised``). ``--action restart-verify`` judges a restart against the witness
with four independent PASS/FAIL/UNVERIFIABLE codes. It never sends a signal,
never synthesizes a service-manager command, and writes only under the
dispatcher directory of the state root.

Output is one JSON object per invocation, through the same ``emit`` contract the
rest of this CLI uses, so a script never has to parse prose.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from project_atlas.orchestration.program.adapters.base import process_start_identity
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
    digest_payload,
    list_checkpoints,
    list_envelopes,
    load_checkpoint,
    load_envelope,
    utc_now,
)
from project_atlas.orchestration.program.decisions import (
    DecisionStatus,
    list_decisions,
    record_answer,
    withdraw_decision,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.path_safety import checked_path, trusted_root
from project_atlas.orchestration.program.reconciliation import reconcile_root
from project_atlas.orchestration.program.resident import (
    _RESTART_CRITERIA,
    _RESTART_PASS,
    DispatcherError,
    DispatcherState,
    ResidentDispatcher,
    RestartWitness,
    _evaluate_restart,
    _process_has_exited,
    _read_restart_command,
    _restart_command_path,
    _restart_verdict_path,
    _restart_witness_path,
    _take_restart_witness,
    _unverifiable_restart_verdict,
    _validate_restart_identity,
    _validate_restart_witness_current,
    clear_pause,
    dispatcher_status,
    read_heartbeat,
    read_restart_witness,
    request_drain,
    request_pause,
    request_stop,
    request_wake,
    write_restart_witness,
)
from project_atlas.orchestration.program.store import write_json_atomic

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
    return checked_path(Path(root).expanduser(), root=_governed_root(args))


def _governed_root(args: argparse.Namespace) -> Path:
    root = (
        getattr(args, "governed_root", None)
        or getattr(args, "state_root", None)
        or getattr(args, "queue_root", None)
    )
    if root is None:
        raise ContinuationError("an explicit root is required", code="STATE_ROOT_REQUIRED")
    return trusted_root(Path(root).expanduser())


def _queue_root(args: argparse.Namespace) -> Path:
    queue_root = getattr(args, "queue_root", None)
    if queue_root is None:
        raise ContinuationError(
            "--queue-root is required: the dispatcher takes work from an "
            "operator-admitted queue and from nowhere else",
            code="QUEUE_ROOT_REQUIRED",
        )
    return checked_path(Path(queue_root).expanduser(), root=_governed_root(args))


# ------------------------------------------------------------------- queue


def cmd_queue(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    queue_root = _queue_root(args)
    action = args.action
    if action == "list":
        queue = load_queue(queue_root, governed_root=_governed_root(args))
        rows = []
        for entry in sorted(queue.entries.values(), key=lambda e: e.program_id):
            try:
                verify_entry(entry, governed_root=_governed_root(args))
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
        program_path = checked_path(Path(args.program).expanduser(), root=_governed_root(args))
        loaded = load_program(program_path, governed_root=_governed_root(args))
        if not getattr(args, "state_root", None):
            # D-2: this used to fall back to the program file's own directory.
            # Under a hardened deployment that directory is mounted READ-ONLY
            # (programs/ sits in ReadOnlyPaths under ProtectSystem=strict), so
            # an admit with no --state-root produced an entry the dispatcher
            # would accept and then be unable to write durable records for.
            #
            # It is the worst shape of failure available here: install succeeds,
            # systemd-analyze sees nothing, the queue reads fine, and the first
            # symptom is a failed write of exactly the records a replacement
            # session needs to resume. So the flag is required rather than
            # defaulted, because a default cannot be the right answer for a
            # path whose writability this command cannot know.
            return {
                "error": (
                    "admit requires --state-root: the state root is where "
                    "durable records are written, and defaulting it to the "
                    "program file's directory silently produces an entry that "
                    "cannot be written to under a read-only deployment"
                ),
                "code": "ADMIT_STATE_ROOT_REQUIRED",
            }, EXIT_USAGE
        state_root = _root(args)
        entry = admit(
            queue_root,
            program_path=program_path,
            program_id=loaded.program.program_id,
            state_root=state_root,
            admitted_by=args.admitted_by,
            reference=args.reference,
            note=args.note or "",
            governed_root=_governed_root(args),
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
        entry = withdraw(
            queue_root, args.program_id, note=args.note or "", governed_root=_governed_root(args)
        )
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
            "note": "Honoured at the next tick boundary; a running program is not interrupted.",
        }, EXIT_OK
    if action == "drain":
        request_drain(root, requested_by=args.requested_by or "operator")
        return {
            "drain_requested": True,
            "note": "The current program finishes, nothing new starts, then the dispatcher exits.",
        }, EXIT_OK
    if action == "wake":
        request_wake(root, reason=args.requested_by or "operator")
        return {"wake_requested": True}, EXIT_OK
    if action == "restart":
        return _cmd_restart(args, root)
    if action == "restart-verify":
        return _cmd_restart_verify(args, root)
    if action == "run":
        queue_root = _queue_root(args)
        dispatcher = ResidentDispatcher(
            root=root,
            queue_root=queue_root,
            governed_root=_governed_root(args),
            checkout=Path(args.checkout).expanduser().resolve()
            if getattr(args, "checkout", None)
            else None,
            registry_root=checked_path(Path(args.registry).expanduser())
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


# ----------------------------------------------------------------- restart
#
# ATLAS-OPERATOR-RECOVERY-FOLLOWUP-001. Three phases, failing closed on
# anything that cannot be verified, and never acquiring a privilege:
#
#   PRE   refuse unless the outgoing dispatcher's identity is established
#         (alive True or False; None refuses), then write a witness.
#   ACT   delegate (default): print the operator commands, as before.
#         supervised: only with an operator-written restart_command; stop is
#         the existing request_drain() plus a bounded wait for the recorded pid
#         to leave under its recorded start identity; start is exactly the
#         recorded argv, without a shell.
#   POST  four independent codes against the witness; exit 0 only when all four
#         are PASS. `restart-verify` runs POST on its own, for a hand restart.
#
# Writes: <state_root>'s dispatcher directory only. No signal is ever sent.

_RESTART_DEFAULT_WAIT_SECONDS = 30.0
_RESTART_MAX_WAIT_SECONDS = 600.0
_RESTART_POLL_SECONDS = 0.1


def _restart_refusal(code: str, error: str, **extra: Any) -> tuple[dict[str, Any], int]:
    return {
        "performed": False,
        "code": code,
        "error": error,
        "model_backed_dispatch": "DISABLED",
        **extra,
    }, EXIT_ERROR


def _wait_until(predicate: Callable[[], bool], seconds: float) -> bool:
    """Poll ``predicate`` until it holds or ``seconds`` pass. Bounded, never spins."""
    deadline = time.monotonic() + seconds
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_RESTART_POLL_SECONDS)


def _write_restart_verdict(
    root: Path,
    witness: RestartWitness | None,
    verdict: dict[str, str],
    evidence: dict[str, list[str]],
) -> Path:
    return write_json_atomic(
        _restart_verdict_path(root),
        {
            "restart_verdict": verdict,
            "evidence": evidence,
            "witness_session_id": (witness.dispatcher_session_id if witness is not None else None),
            "witness_digest": (
                digest_payload(witness.model_dump(mode="json")) if witness is not None else None
            ),
            "verified_at": utc_now(),
            "model_backed_dispatch": "DISABLED",
        },
    )


def _all_pass(verdict: dict[str, str]) -> bool:
    return all(verdict.get(name) == _RESTART_PASS for name in _RESTART_CRITERIA)


def _cmd_restart(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    """Serialize operator restarts; a contender must not start a second child."""
    from project_atlas.orchestration.program.process_lock import (
        ProcessLockError,
        exclusive_process_lock,
    )
    from project_atlas.orchestration.program.resident import dispatcher_dir

    # Preserve argument/identity refusals without making even a lock file.
    if getattr(args, "mode", None) != "supervised" or _read_restart_command(root) is None:
        return _cmd_restart_impl(args, root)
    beat = read_heartbeat(root)
    if beat is None:
        return _cmd_restart_impl(args, root)
    try:
        _validate_restart_identity(beat.pid, beat.process_start_identity)
    except DispatcherError as exc:
        return _restart_refusal(exc.code, str(exc), stopped=False, started=False)
    try:
        with exclusive_process_lock(dispatcher_dir(root) / "restart.lock"):
            return _cmd_restart_impl(args, root)
    except ProcessLockError as exc:
        return _restart_refusal(
            "RESTART_ALREADY_IN_PROGRESS", str(exc), stopped=False, started=False
        )


def _cmd_restart_impl(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    requested_mode = getattr(args, "mode", None) or "delegate"
    mode: Literal["delegate", "supervised"]
    if requested_mode == "delegate":
        mode = "delegate"
    elif requested_mode == "supervised":
        mode = "supervised"
    else:
        return {
            "error": f"unknown restart mode {requested_mode}",
            "code": "RESTART_MODE_UNKNOWN",
        }, EXIT_USAGE
    raw_wait = getattr(args, "wait_seconds", None)
    # `is None`, not truthiness: an explicit 0 is out of bounds, not "use the default".
    wait_seconds = float(_RESTART_DEFAULT_WAIT_SECONDS if raw_wait is None else raw_wait)
    if not 0 < wait_seconds <= _RESTART_MAX_WAIT_SECONDS:
        return {
            "error": (
                f"--wait-seconds must be in (0, {_RESTART_MAX_WAIT_SECONDS:g}]; "
                f"got {wait_seconds:g}"
            ),
            "code": "RESTART_WAIT_SECONDS_OUT_OF_BOUNDS",
        }, EXIT_USAGE
    queue_root = (
        _queue_root(args) if getattr(args, "queue_root", None) else None
    )

    command: tuple[str, ...] | None = None
    if mode == "supervised":
        # Checked first, and without looking at any process: supervised mode
        # without a declaration has nothing it could run, and it never guesses.
        command = _read_restart_command(root)
        if command is None:
            return _restart_refusal(
                "RESTART_COMMAND_NOT_DECLARED",
                "--mode supervised requires an operator-written restart_command "
                f"at {_restart_command_path(root)}; none is declared, and no "
                "command is synthesized or guessed in its place. Nothing was "
                "stopped.",
                stopped=False,
                started=False,
            )

    # ---- PRE
    try:
        witness = _take_restart_witness(
            root, mode=mode, queue_root=queue_root, governed_root=_governed_root(args)
        )
    except DispatcherError as exc:
        if exc.code != "RESTART_IDENTITY_UNVERIFIABLE":
            raise
        return _restart_refusal(exc.code, str(exc), stopped=False, started=False)
    witness_path = _restart_witness_path(root)
    # A stale witness must not survive a failed write and be judged against.
    witness_path.unlink(missing_ok=True)
    write_restart_witness(root, witness)

    verify_command = f"atlas program dispatcher --state-root {root} --action restart-verify"
    if queue_root is not None:
        verify_command += f" --queue-root {queue_root}"

    if mode == "delegate":
        return {
            "performed": False,
            "reason": "NOT_AUTHORIZED_FROM_HERE",
            "mode": "delegate",
            "witness_path": str(witness_path),
            "witness": witness.model_dump(mode="json"),
            "operator_commands": [
                f"atlas program dispatcher --state-root {root} --action drain",
                "# wait for terminal_reason=OPERATOR_DRAIN in the heartbeat, then:",
                f"atlas program dispatcher --state-root {root} "
                f"--queue-root <QUEUE_ROOT> --action run",
                "# then judge the restart against the witness taken just now:",
                verify_command,
            ],
            "note": (
                "Delegate mode stops and starts nothing. The witness is taken so "
                "a hand restart can still be verified per criterion. No service "
                "is installed by this package; if one is installed later, the "
                "operator restarts it through the service manager."
            ),
            "model_backed_dispatch": "DISABLED",
        }, EXIT_OK

    # ---- ACT (supervised)
    assert command is not None
    stop: dict[str, Any] = {
        "outgoing_pid": witness.pid,
        "outgoing_process_start_identity": witness.process_start_identity,
        "alive_at_witness": witness.alive_at_witness,
        "signal_sent": False,
    }
    if witness.alive_at_witness:
        try:
            _validate_restart_witness_current(root, witness)
        except DispatcherError as exc:
            return _restart_refusal(exc.code, str(exc), stopped=False, started=False)
        request_drain(root, requested_by=args.requested_by or "operator:restart")
        request_wake(root, reason="restart: drain requested")
        stop["drain_requested"] = True
        exited = _wait_until(
            lambda: _process_has_exited(witness.pid, witness.process_start_identity),
            wait_seconds,
        )
        stop["exited"] = exited
        if not exited:
            return _restart_refusal(
                "RESTART_STOP_NOT_OBSERVED",
                f"drain was requested but pid {witness.pid} was still running "
                f"under its recorded start identity after {wait_seconds:g}s. "
                "Nothing was started, so two dispatchers never run at once. The "
                "drain request is left in place.",
                stopped=False,
                started=False,
                witness_path=str(witness_path),
                stop=stop,
            )
    else:
        stop["drain_requested"] = False
        stop["exited"] = True

    # F-02: draining/waiting may have outlived the PID ownership observation.
    try:
        _validate_restart_witness_current(root, witness)
    except DispatcherError as exc:
        return _restart_refusal(exc.code, str(exc), stopped=False, started=False)

    flags = 0
    if os.name == "nt":
        flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(
            getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    try:
        proc = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=os.name != "nt",
            creationflags=flags,
        )
    except OSError as exc:
        return _restart_refusal(
            "RESTART_START_FAILED",
            f"the declared restart_command could not be started: {exc}",
            stopped=True,
            started=False,
            witness_path=str(witness_path),
            stop=stop,
        )
    start = {
        "argv": list(command),
        "pid": proc.pid,
        "process_start_identity": process_start_identity(proc.pid) or "unknown",
        "shell": False,
    }

    def _published() -> bool:
        code = proc.poll()
        if code is not None and code != 0:
            return True
        try:
            beat = read_heartbeat(root)
        except DispatcherError:
            return False
        return (
            beat is not None
            and beat.dispatcher_session_id != witness.dispatcher_session_id
            and beat.ticks >= 1
        )

    start["new_heartbeat_observed"] = _wait_until(_published, wait_seconds)
    start["exit_status_so_far"] = proc.poll()

    # ---- POST
    verdict, evidence = _evaluate_restart(
        root, witness, queue_root=queue_root, governed_root=_governed_root(args)
    )
    verdict_path = _write_restart_verdict(root, witness, verdict, evidence)
    return {
        "performed": True,
        "mode": "supervised",
        "stopped": True,
        "started": True,
        "witness_path": str(witness_path),
        "verdict_path": str(verdict_path),
        "stop": stop,
        "start": start,
        "restart_verdict": verdict,
        "evidence": evidence,
        "note": (
            "The verdict is a point-in-time judgement against the witness. "
            f"Re-run `{verify_command}` to judge again later."
        ),
        "model_backed_dispatch": "DISABLED",
    }, (EXIT_OK if _all_pass(verdict) else EXIT_ERROR)


def _cmd_restart_verify(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    queue_root = (
        _queue_root(args) if getattr(args, "queue_root", None) else None
    )
    witness: RestartWitness | None
    try:
        witness = read_restart_witness(root)
        why = (
            "no restart witness has been written under this state root; a "
            "restart that was not witnessed cannot be verified"
        )
    except DispatcherError as exc:
        witness = None
        why = f"{exc.code}: {exc}"
    if witness is None:
        verdict, evidence = _unverifiable_restart_verdict(why)
    else:
        verdict, evidence = _evaluate_restart(
            root, witness, queue_root=queue_root, governed_root=_governed_root(args)
        )
    verdict_path = _write_restart_verdict(root, witness, verdict, evidence)
    return {
        "restart_verdict": verdict,
        "evidence": evidence,
        "witness_path": str(_restart_witness_path(root)),
        "verdict_path": str(verdict_path),
        "witness": witness.model_dump(mode="json") if witness is not None else None,
        "model_backed_dispatch": "DISABLED",
    }, (EXIT_OK if _all_pass(verdict) else EXIT_ERROR)


# ----------------------------------------------------------------- capsule


def cmd_capsule(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = _root(args)
    queue_root = (
        _queue_root(args) if getattr(args, "queue_root", None) else None
    )
    capsule = build_capsule(
        root,
        for_worker_id=args.worker_id or "unassigned",
        queue_root=queue_root,
        governed_root=_governed_root(args),
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
            "checkpoints": [c.model_dump(mode="json") for c in list_checkpoints(root)],
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
        # The queue is consulted for the same reason the capsule consults it:
        # a task with no checkpoint whose program is recorded COMPLETE is a
        # lost record, and the two surfaces must reach the same disposition.
        queue_root = (
            _queue_root(args)
            if getattr(args, "queue_root", None)
            else None
        )
        verdicts = reconcile_root(
            root,
            our_worker_id=args.worker_id or "unassigned",
            queue_root=queue_root,
            governed_root=_governed_root(args),
        )
        return {
            "state_root": str(root),
            "queue_root": str(queue_root) if queue_root is not None else None,
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
        # Guidance only: schema compatibility and quiescence are not observed
        # by this command. Additive directories do not imply safe downgrade.
        from shlex import quote

        from project_atlas.orchestration.program.continuation import CHECKPOINT_SCHEMA_VERSION

        command = (
            "atlas program dispatcher "
            f"--governed-root {quote(str(_governed_root(args)))} "
            f"--state-root {quote(str(root))}"
        )
        return {
            "performed": False,
            "reason": "NOT_AUTHORIZED_FROM_HERE",
            "preconditions_verified": False,
            "checkpoint_reader_schema": CHECKPOINT_SCHEMA_VERSION,
            "automatic_migration": False,
            "operator_procedure": [
                f"1. Withhold new work: {command} --action pause. Record the "
                "approved target revision and current installed module provenance.",
                f"2. Request drain: {command} --action drain. Observe status with "
                f"{command} --action status; confirm OPERATOR_DRAIN and actual "
                "exit under the recorded PID AND start identity, with no owned workers. "
                "A submitted sentinel is not proof of exit; unknown means stop.",
                "3. Preserve a byte-complete quiescent snapshot of queue-referenced "
                "state, checkpoints, envelopes, decisions, launch evidence, approved "
                "program bytes and registry/workspace bindings; verify hashes and "
                "retain the original writer revision and compatible reader environment.",
                f"4. Require a compatible reader for the actual schemas before "
                f"repointing code. This checkpoint reader uses schema {CHECKPOINT_SCHEMA_VERSION}; "
                "other explicit versions fail closed as CHECKPOINT_VERSION_SKEW. "
                "Historical readers may report CHECKPOINT_MALFORMED. No automatic "
                "upgrade/downgrade or migration is provided; never delete, relabel "
                "or reseal records to bypass refusal.",
                "5. Only after compatibility checks on preserved copies, install "
                "the approved revision non-editably using the release procedure. "
                "Preserve the explicit governed root and absolute bindings; "
                "copying JSON does not relocate paths automatically.",
                "6. Restart with pause retained; verify installed module origin and "
                "expected HEAD/TREE, checkpoint seals/sequences, completed-task zero "
                "replay and uncertain quarantine. Resume only by a separate "
                "operator act after all gates hold.",
            ],
            "state_compatibility": "REQUIRES_COMPATIBLE_READER",
            "note": (
                "No rollback, snapshot, reader check, service action or reboot was "
                "performed. Records and reader environments must be preserved; "
                "printed guidance and a reconciliation lens do not grant authority."
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


CONTINUATION_HANDLERS: dict[str, Any] = {
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
            (
                "status",
                "run",
                "pause",
                "resume",
                "stop",
                "drain",
                "wake",
                "restart",
                "restart-verify",
            ),
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
        child.add_argument(
            "--governed-root",
            type=Path,
            default=None,
            help="Explicit boundary containing state, queue, programs and workspaces",
        )
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
        child.add_argument("--status", default=None, choices=[s.value for s in DecisionStatus])
        child.add_argument("--checkout", type=Path, default=None)
        child.add_argument("--registry", type=Path, default=None)
        child.add_argument("--tick-seconds", type=float, default=5.0)
        child.add_argument("--max-ticks", type=int, default=None)
        child.add_argument("--max-seconds", type=float, default=None)
        child.add_argument("--exit-when-drained", action="store_true")
        if name == "dispatcher":
            child.add_argument(
                "--mode",
                choices=("delegate", "supervised"),
                default="delegate",
                help=(
                    "restart only. delegate (default): witness, then print the "
                    "operator commands. supervised: witness, drain, then run the "
                    "operator-declared restart_command, then verify."
                ),
            )
            child.add_argument(
                "--wait-seconds",
                type=float,
                default=_RESTART_DEFAULT_WAIT_SECONDS,
                help=(
                    "restart --mode supervised only: bound on waiting for the old "
                    f"dispatcher to exit and the new one to publish (max "
                    f"{_RESTART_MAX_WAIT_SECONDS:g})."
                ),
            )


__all__ = [
    "CONTINUATION_HANDLERS",
    "DispatcherState",
    "register_continuation_commands",
]
