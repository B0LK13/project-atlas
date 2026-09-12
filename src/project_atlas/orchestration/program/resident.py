"""The resident dispatcher: a model-free process that outlives every program.

``ProgramSupervisor`` is finite by design and that is correct -- it executes one
approved program until ``PROGRAM_COMPLETE`` and exits. What has been missing is
the thing *above* it: a process that stays resident, notices when an operator
admits new approved work, runs the finite supervisor for it, and otherwise
waits without burning the machine or inventing something to do.

Three properties, each a refusal:

**It does not spin.** Idle time is spent asleep, in bounded quanta, not in a
loop of state reads. What "efficient" means here is stated exactly rather than
implied: one ``stat`` of the wake sentinel per quantum (default 0.5s) and one
queue read per tick (default 5s). It is not an ``inotify`` subscription and
does not claim to be -- a portable blocking primitive that works on Linux,
macOS and Windows and survives a network filesystem does not exist, and a
Linux-only wake would make this layer untestable on the platforms the rest of
this package already supports. The honest measure is CPU time consumed while
idle, which the acceptance test measures directly.

**It does not restart completed programs.** A queue entry that reached
``COMPLETE`` is terminal, and ``approved_queue.update_entry`` refuses to return
it to a runnable status. The dispatcher never re-reads a finished program and
decides to "check it once more".

**It does not invent work.** There is exactly one source of tasks -- programs
an operator admitted to the approved-work queue -- and no discovery path. When
the queue is empty the dispatcher waits. It does not scan the backlog, it does
not propose anything, and it does not manufacture filler to look productive.

It publishes what an operator or a replacement session needs to know without
asking it anything: health, heartbeat, the revision it is running, its process
start identity, pause state and terminal reason.

MODEL_BACKED_DISPATCH is disabled: this module launches adapters, and every
adapter it is validated with is a zero-model fixture. Nothing here makes a
paid call, and the envelope budgets default ``max_model_calls`` to zero.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program.adapters.base import process_start_identity
from project_atlas.orchestration.program.approved_queue import (
    ApprovedWorkQueue,
    QueueEntry,
    QueueEntryStatus,
    QueueError,
    load_queue,
    update_entry,
    verify_entry,
)
from project_atlas.orchestration.program.blocked_work import handle_blocked_task
from project_atlas.orchestration.program.continuation import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    ContinuationError,
    load_envelope,
    new_session_id,
    read_durable,
    utc_now,
)
from project_atlas.orchestration.program.continuation_projection import (
    materialise_envelopes,
    project_checkpoints,
)
from project_atlas.orchestration.program.decisions import (
    DecisionKind,
    blocked_task_ids,
    raise_decision,
)
from project_atlas.orchestration.program.enrollment import AgentStatus, load_registry
from project_atlas.orchestration.program.loader import (
    LoadedProgram,
    ProgramLoadError,
    load_program,
)
from project_atlas.orchestration.program.models import ProgramError, ProgramStopReason
from project_atlas.orchestration.program.store import (
    append_event,
    load_state,
    state_dir,
    write_json_atomic,
)
from project_atlas.orchestration.program.supervisor import ProgramSupervisor, SupervisorReport

DISPATCHER_DIR: Final[str] = "dispatcher"
HEARTBEAT_NAME: Final[str] = "heartbeat.json"
#: Re-read every quantum while the dispatcher sleeps, so an admit is noticed
#: without the dispatcher having to be interrupted.
WAKE_NAME: Final[str] = "dispatcher.wake"
#: Re-read every tick. Same two-mechanism shape the program pause already uses,
#: and for the same reason: a flag held in memory by a running process is a
#: flag that process will overwrite.
PAUSE_NAME: Final[str] = "dispatcher.pause"
STOP_NAME: Final[str] = "dispatcher.stop"
#: Written on request and honoured after the current program finishes. Distinct
#: from stop, which does not wait.
DRAIN_NAME: Final[str] = "dispatcher.drain"

#: Stop reasons that mean the program is finished and must never be re-run.
_TERMINAL_PROGRAM_STOPS: Final[frozenset[ProgramStopReason]] = frozenset(
    {ProgramStopReason.PROGRAM_COMPLETE}
)
#: Stop reasons that mean a person has to look. The entry is quarantined: the
#: dispatcher will not pick it up again, and it does not re-ask.
_QUARANTINE_STOPS: Final[frozenset[ProgramStopReason]] = frozenset(
    {
        ProgramStopReason.RECONCILE_REQUIRED,
        ProgramStopReason.HARD_BLOCKER,
        ProgramStopReason.CANCELLED,
    }
)
#: Stop reasons that route to the durable decision queue, once, by kind.
_DECISION_STOPS: Final[dict[ProgramStopReason, DecisionKind]] = {
    ProgramStopReason.OWNER_DECISION_REQUIRED: DecisionKind.PERMISSION,
    ProgramStopReason.LIMIT_REACHED: DecisionKind.BUDGET_INCREASE,
    ProgramStopReason.CYCLE_BUDGET_REACHED: DecisionKind.BUDGET_INCREASE,
    ProgramStopReason.RECONCILE_REQUIRED: DecisionKind.UNCERTAIN_EXTERNAL_EFFECT,
    ProgramStopReason.HARD_BLOCKER: DecisionKind.SCOPE_EXPANSION,
}


class DispatcherError(ContinuationError):
    code = "DISPATCHER_ERROR"


class DispatcherState(StrEnum):
    """What the dispatcher is doing right now. Published, not inferred."""

    STARTING = "STARTING"
    #: A finite supervisor is running under this dispatcher.
    RUNNING_PROGRAM = "RUNNING_PROGRAM"
    #: Approved work exists but none of it is runnable right now.
    WAITING_ON_WORK = "WAITING_ON_WORK"
    #: The queue holds nothing runnable. Sleeping.
    IDLE_EMPTY_QUEUE = "IDLE_EMPTY_QUEUE"
    PAUSED = "PAUSED"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class DispatcherStopReason(StrEnum):
    """Why the resident loop ended. Always published before exit."""

    OPERATOR_STOP = "OPERATOR_STOP"
    OPERATOR_DRAIN = "OPERATOR_DRAIN"
    TICK_BUDGET_REACHED = "TICK_BUDGET_REACHED"
    DEADLINE_REACHED = "DEADLINE_REACHED"
    #: Every admitted program reached a terminal state. The dispatcher may
    #: still be configured to stay resident; this reason is only used when it
    #: was asked to exit once there is nothing left.
    QUEUE_DRAINED = "QUEUE_DRAINED"
    #: The approved-work queue could not be read at all. Distinct from
    #: QUEUE_DRAINED, which means it was read and held nothing runnable, and
    #: deliberately distinct from TICK_BUDGET_REACHED: an independent verifier
    #: observed that reporting "ran out of ticks" for an unreadable
    #: authoritative input reads as a benign timeout, which is exactly what a
    #: slow or busy queue also produces. A dispatcher whose only source of work
    #: is unreadable has nothing it could ever discover by waiting, so it stops
    #: and says why rather than burning its whole tick budget in silence.
    QUEUE_UNREADABLE = "QUEUE_UNREADABLE"
    FATAL_ERROR = "FATAL_ERROR"


class Heartbeat(BaseModel):
    """The dispatcher's published health. Written every tick, atomically.

    A heartbeat with a pid and no start identity is a heartbeat that cannot be
    told apart from a stranger on a reused pid, so both travel together here
    exactly as they do everywhere else in this package.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    dispatcher_session_id: str = Field(min_length=1, max_length=190)
    pid: int = Field(ge=0, le=2**31 - 1)
    process_start_identity: str = Field(min_length=1, max_length=256)
    hostname: str = Field(default="", max_length=256)
    #: The revision of the checkout this dispatcher is running from. Published
    #: so a restart can be seen to have come back on the same pinned code.
    revision_head: str = Field(default="", max_length=64)
    revision_tree: str = Field(default="", max_length=64)
    started_at: str
    beat_at: str = Field(default_factory=utc_now)
    ticks: int = Field(default=0, ge=0, le=1_000_000_000)
    state: DispatcherState = DispatcherState.STARTING
    paused: bool = False
    pause_requested_by: str | None = None
    current_program_id: str | None = None
    last_program_stop_reason: str | None = None
    #: Whether the last tick could READ the approved-work queue, and why not.
    #: Published because "the queue is empty" and "the queue could not be read"
    #: are different facts that otherwise present identically from outside: an
    #: idle dispatcher and a dispatcher staring at a corrupt manifest both show
    #: zero launches. An independent verifier hit exactly that.
    queue_status: str = "UNKNOWN"
    queue_error: str | None = Field(default=None, max_length=1024)
    queue_error_code: str | None = Field(default=None, max_length=64)
    terminal_reason: DispatcherStopReason | None = None
    #: Cumulative, across this dispatcher process only.
    programs_started: int = Field(default=0, ge=0, le=1_000_000)
    launches: int = Field(default=0, ge=0, le=1_000_000)
    model_calls: Literal[0] = 0
    model_backed_dispatch: Literal["DISABLED"] = "DISABLED"
    truth_boundary: str = TRUTH_BOUNDARY


@dataclass
class TickResult:
    """One pass of the resident loop. Evidence, never authority."""

    tick: int
    state: DispatcherState
    program_id: str | None = None
    report: SupervisorReport | None = None
    launched: int = 0
    slept_seconds: float = 0.0
    #: READABLE / UNREADABLE / UNKNOWN. Distinct from "nothing runnable".
    queue_status: str = "UNKNOWN"
    queue_error: str | None = None
    #: The refusal's own code -- QUEUE_UNREADABLE for bytes that are not JSON,
    #: QUEUE_SCHEMA_INVALID for JSON that is not this schema. Kept apart
    #: because they mean different things to an operator: the first is a
    #: damaged file, the second is a file written by something with a
    #: different idea of the schema, which is a version problem and not a
    #: corruption one.
    queue_error_code: str | None = None
    notes: list[str] = field(default_factory=list)
    decisions_raised: list[str] = field(default_factory=list)


def dispatcher_dir(root: Path) -> Path:
    return state_dir(root) / DISPATCHER_DIR


def heartbeat_path(root: Path) -> Path:
    return dispatcher_dir(root) / HEARTBEAT_NAME


def read_heartbeat(root: Path) -> Heartbeat | None:
    path = heartbeat_path(root)
    if not path.is_file():
        return None
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatcherError(
            f"dispatcher heartbeat at {path} is unreadable: {exc}",
            code="HEARTBEAT_UNREADABLE",
        ) from exc
    return read_durable(
        Heartbeat,
        raw,
        path=path,
        error=DispatcherError,
        code="HEARTBEAT_SCHEMA_INVALID",
        what="dispatcher heartbeat",
    )


def request_wake(root: Path, *, reason: str = "new approved work") -> Path:
    """Ask a sleeping dispatcher to look again, now rather than at its next tick.

    Written by ``queue admit`` and by the operator. A wake is a hint, never an
    instruction: it shortens a sleep, it does not decide what runs. A wake for
    a queue with nothing runnable simply produces one more idle tick.
    """
    target = dispatcher_dir(root) / WAKE_NAME
    return write_json_atomic(target, {"at": utc_now(), "reason": reason})


def consume_wake(root: Path) -> bool:
    """Take the wake if one is pending. Once-only, like every other signal here."""
    target = dispatcher_dir(root) / WAKE_NAME
    if not target.is_file():
        return False
    try:
        target.unlink()
    except OSError:
        return False
    return True


def request_pause(root: Path, *, requested_by: str) -> Path:
    """Withhold new program dispatch. A running program is left to finish."""
    return write_json_atomic(
        dispatcher_dir(root) / PAUSE_NAME,
        {"at": utc_now(), "requested_by": requested_by},
    )


def clear_pause(root: Path) -> bool:
    target = dispatcher_dir(root) / PAUSE_NAME
    if not target.is_file():
        return False
    target.unlink()
    return True


def pause_requested(root: Path) -> dict[str, Any] | None:
    """The pause record, re-read from disk every tick. None when not paused."""
    target = dispatcher_dir(root) / PAUSE_NAME
    if not target.is_file():
        return None
    import json

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A torn pause record still means somebody asked for a pause. Failing
        # closed here means honouring it, not ignoring it.
        return {"at": "unknown", "requested_by": "unknown"}
    return raw if isinstance(raw, dict) else {"at": "unknown", "requested_by": "unknown"}


def request_stop(root: Path, *, requested_by: str) -> Path:
    """Stop at the next tick boundary. Does not interrupt a running program."""
    return write_json_atomic(
        dispatcher_dir(root) / STOP_NAME, {"at": utc_now(), "requested_by": requested_by}
    )


def request_drain(root: Path, *, requested_by: str) -> Path:
    """Finish the current program, start nothing new, then exit."""
    return write_json_atomic(
        dispatcher_dir(root) / DRAIN_NAME,
        {"at": utc_now(), "requested_by": requested_by},
    )


def clear_signals(root: Path) -> None:
    """Clear stop and drain. Deliberately not pause: pause is operator state.

    Called at start-up so a stop left behind by a previous run cannot make the
    next one exit immediately. A pause, in contrast, is a decision that should
    survive a restart -- clearing it would resume work an operator withheld.
    """
    for name in (STOP_NAME, DRAIN_NAME, WAKE_NAME):
        try:
            (dispatcher_dir(root) / name).unlink(missing_ok=True)
        except OSError:
            continue


def _git_revision(checkout: Path) -> tuple[str, str]:
    """HEAD and TREE of the checkout this dispatcher runs from.

    Published rather than assumed. A restart that came back on different code
    is a fact an operator needs to see in the heartbeat, not discover later.
    Failure to read them yields empty strings -- an unknown revision is
    reported as unknown and never guessed.
    """
    def _run(args: list[str]) -> str:
        try:
            completed = subprocess.run(
                args,
                cwd=str(checkout),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if completed.returncode != 0:
            return ""
        return (completed.stdout or "").strip()

    return _run(["git", "rev-parse", "HEAD"]), _run(["git", "rev-parse", "HEAD^{tree}"])


class ResidentDispatcher:
    """A model-free resident process above the finite program runner."""

    def __init__(
        self,
        *,
        root: Path,
        queue_root: Path,
        checkout: Path | None = None,
        registry_root: Path | None = None,
        tick_seconds: float = 5.0,
        wake_quantum_seconds: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        supervisor_factory: Callable[[Any, Path], ProgramSupervisor] | None = None,
    ) -> None:
        if wake_quantum_seconds <= 0:
            raise DispatcherError(
                "wake quantum must be positive; a zero quantum is a spin loop",
                code="DISPATCHER_BAD_QUANTUM",
            )
        if tick_seconds < wake_quantum_seconds:
            raise DispatcherError(
                "tick interval must be at least one wake quantum",
                code="DISPATCHER_BAD_TICK",
            )
        self.root = root.resolve()
        self.queue_root = queue_root.resolve()
        self.checkout = (checkout or Path.cwd()).resolve()
        self.registry_root = registry_root
        self.tick_seconds = tick_seconds
        self.wake_quantum_seconds = wake_quantum_seconds
        self._clock = clock
        self._sleep = sleeper
        self._supervisor_factory = supervisor_factory
        self.session_id = new_session_id("dispatcher")
        self._ticks = 0
        self._last_queue_status = "UNKNOWN"
        self._last_queue_error: str | None = None
        self._last_queue_error_code: str | None = None
        self._last_notes: list[str] = []
        self._programs_started = 0
        self._launches = 0
        self._started_at = utc_now()
        head, tree = _git_revision(self.checkout)
        pid = os.getpid()
        self._heartbeat = Heartbeat(
            dispatcher_session_id=self.session_id,
            pid=pid,
            process_start_identity=process_start_identity(pid) or "unknown",
            hostname=os.uname().nodename if hasattr(os, "uname") else "",
            revision_head=head,
            revision_tree=tree,
            started_at=self._started_at,
        )

    # ------------------------------------------------------------- publishing

    def publish(
        self,
        *,
        state: DispatcherState,
        program_id: str | None = None,
        last_stop: str | None = None,
        terminal: DispatcherStopReason | None = None,
        queue_status: str | None = None,
        queue_error: str | None = None,
        queue_error_code: str | None = None,
    ) -> Heartbeat:
        """Write the heartbeat. Atomic, so a reader never sees a torn one."""
        pause = pause_requested(self.root)
        beat = self._heartbeat
        beat.beat_at = utc_now()
        beat.ticks = self._ticks
        beat.state = state
        beat.paused = pause is not None
        beat.pause_requested_by = (
            str(pause.get("requested_by")) if pause is not None else None
        )
        beat.current_program_id = program_id
        if queue_status is not None:
            beat.queue_status = queue_status
            beat.queue_error = queue_error
            beat.queue_error_code = queue_error_code
        if last_stop is not None:
            beat.last_program_stop_reason = last_stop
        beat.terminal_reason = terminal
        beat.programs_started = self._programs_started
        beat.launches = self._launches
        write_json_atomic(heartbeat_path(self.root), beat.model_dump(mode="json"))
        return beat

    # ------------------------------------------------------------- selection

    def _select(self, queue: ApprovedWorkQueue) -> tuple[QueueEntry | None, list[str]]:
        """The next runnable admitted program, or nothing, with the reasons.

        Never invents work. An entry whose pinned bytes changed is skipped and
        the reason is recorded rather than the entry being run anyway -- the
        approval was for the bytes, not for the path.
        """
        notes: list[str] = []
        for entry in queue.runnable():
            try:
                verify_entry(entry)
            except QueueError as exc:
                notes.append(f"{entry.program_id}: skipped -- {exc}")
                continue
            return entry, notes
        return None, notes

    # ------------------------------------------------------------------ tick

    def tick(self) -> TickResult:
        """One pass: read the queue, run at most one program, or wait."""
        self._ticks += 1
        result = TickResult(tick=self._ticks, state=DispatcherState.IDLE_EMPTY_QUEUE)

        if pause_requested(self.root) is not None:
            result.state = DispatcherState.PAUSED
            result.notes.append(
                "paused: no new program will be dispatched; a program already "
                "running is left to finish"
            )
            self.publish(state=DispatcherState.PAUSED)
            return result

        try:
            queue = load_queue(self.queue_root)
        except QueueError as exc:
            result.state = DispatcherState.WAITING_ON_WORK
            code = getattr(exc, "code", "APPROVED_QUEUE_ERROR")
            result.queue_status = "UNREADABLE"
            result.queue_error = str(exc)
            result.queue_error_code = code
            result.notes.append(f"{code}: nothing dispatched -- {exc}")
            self.publish(
                state=DispatcherState.WAITING_ON_WORK,
                queue_status="UNREADABLE",
                queue_error=str(exc),
                queue_error_code=code,
            )
            return result

        entry, notes = self._select(queue)
        result.notes.extend(notes)
        result.queue_status = "READABLE"
        if entry is None:
            result.state = DispatcherState.IDLE_EMPTY_QUEUE
            self.publish(
                state=DispatcherState.IDLE_EMPTY_QUEUE, queue_status="READABLE"
            )
            return result

        result.program_id = entry.program_id
        result.state = DispatcherState.RUNNING_PROGRAM
        self.publish(
            state=DispatcherState.RUNNING_PROGRAM,
            program_id=entry.program_id,
            queue_status="READABLE",
        )
        report = self._run_entry(entry, result)
        result.report = report
        return result

    def _run_entry(self, entry: QueueEntry, result: TickResult) -> SupervisorReport | None:
        """Run one finite program to its stop reason, then settle the queue."""
        state_root = Path(entry.state_root)
        try:
            loaded = load_program(Path(entry.program_path))
        except ProgramLoadError as exc:
            update_entry(
                self.queue_root,
                entry.program_id,
                status=QueueEntryStatus.QUARANTINED,
                last_stop_reason="PROGRAM_UNLOADABLE",
                note=str(exc),
            )
            result.notes.append(f"{entry.program_id}: quarantined -- {exc}")
            return None

        skip = blocked_task_ids(state_root)
        if skip:
            result.notes.append(
                f"{entry.program_id}: {len(skip)} task(s) have an open operator "
                "decision and will not be re-asked: " + ", ".join(sorted(skip))
            )

        # An envelope per approved task, BEFORE anything launches. A task with
        # no recorded authority is a task a replacement session cannot
        # reconstruct, and the moment to write it is before the work, not after.
        head, tree = _git_revision(loaded.workspace)
        materialise_envelopes(
            loaded,
            state_root,
            candidate_head=head or loaded.program.base_pin,
            candidate_tree=tree or loaded.program.base_pin,
        )

        # D5: the resident path threaded `registry_root` but never passed
        # `enrolled_agents`, so `_apply_enrollments` never ran, the program's
        # profiles kept their placeholder agent ids, and EVERY task was held
        # with "no active enrolled agent is bound" -- even with an ACTIVE,
        # correctly assigned agent in the registry. It failed closed, which is
        # safe, but a registry-configured deployment could never dispatch at
        # all. The finite `program start` path bound enrolments all along; only
        # this one did not, which is why no test caught it.
        enrolled = self._enrolled_for(loaded)
        supervisor = (
            self._supervisor_factory(loaded, state_root)
            if self._supervisor_factory is not None
            else ProgramSupervisor(
                loaded,
                state_root=state_root,
                enrolled_agents=enrolled,
                registry_root=self.registry_root,
            )
        )
        update_entry(
            self.queue_root,
            entry.program_id,
            status=QueueEntryStatus.RUNNING,
            increment_runs=True,
        )
        self._programs_started += 1
        append_event(
            state_root,
            "DISPATCHER_PROGRAM_STARTED",
            {
                "program_id": entry.program_id,
                "dispatcher_session_id": self.session_id,
                "tick": self._ticks,
                "model_backed_dispatch": "DISABLED",
            },
        )
        try:
            report = supervisor.start()
        except ProgramError as exc:
            # D3: previously only ProgramLoadError was caught, so a
            # ProgramError raised by start() -- PROGRAM_MISMATCH, for instance,
            # when two admitted programs share one state root -- escaped
            # tick() and run(), the CLI exited non-zero, and a service manager
            # restarted straight back into the identical error until its start
            # limit tripped. One misconfigured entry took down the whole
            # resident dispatcher. An entry the supervisor refuses is a
            # quarantine case, exactly like an unloadable one.
            code = getattr(exc, "code", "PROGRAM_ERROR")
            update_entry(
                self.queue_root,
                entry.program_id,
                status=QueueEntryStatus.QUARANTINED,
                last_stop_reason=code,
                note=str(exc),
            )
            result.notes.append(
                f"{entry.program_id}: quarantined on {code} -- {exc}"
            )
            append_event(
                state_root,
                "DISPATCHER_PROGRAM_REFUSED",
                {"program_id": entry.program_id, "code": code, "detail": str(exc)},
            )
            return None
        self._launches += report.launches_this_run
        result.launched = report.launches_this_run
        self._project(loaded, state_root, result, head=head, tree=tree)
        self._settle(entry, report, state_root, result)
        return report

    def _project(
        self,
        loaded: Any,
        state_root: Path,
        result: TickResult,
        *,
        head: str,
        tree: str,
    ) -> None:
        """Project durable supervisor state into continuation checkpoints.

        Failures here are recorded and do not fail the tick. A projection is a
        convenience for the next session, and losing it must not turn a
        completed program into an error -- the authoritative records
        (``state.json``, ``events.jsonl``) are already written either way.
        """
        state = load_state(state_root)
        if state is None:
            return
        try:
            written = project_checkpoints(
                loaded,
                state_root,
                state=state,
                session_id=self.session_id,
                worktree=loaded.workspace,
                git_head=head or loaded.program.base_pin,
                git_tree=tree or loaded.program.base_pin,
            )
        except ContinuationError as exc:
            result.notes.append(f"checkpoint projection refused: {exc}")
            return
        result.notes.append(
            f"projected {len(written)} continuation checkpoint(s) from durable state"
        )

    def _settle(
        self,
        entry: QueueEntry,
        report: SupervisorReport,
        state_root: Path,
        result: TickResult,
    ) -> None:
        """Turn one program's stop reason into durable queue and decision state.

        This is where the non-blocking rule lives. A stop that is really a
        question for a person becomes exactly one durable decision record, the
        entry stops being runnable, and the dispatcher moves on to whatever
        else is admitted. It does not re-run the program to re-discover the
        same blocker, and it does not raise the question a second time.
        """
        stop = report.stop_reason
        append_event(
            state_root,
            "DISPATCHER_PROGRAM_STOPPED",
            {
                "program_id": entry.program_id,
                "stop_reason": stop.value,
                "launches_this_run": report.launches_this_run,
                "program_complete": report.complete,
                "dispatcher_session_id": self.session_id,
            },
        )

        if stop in _TERMINAL_PROGRAM_STOPS and report.complete:
            update_entry(
                self.queue_root,
                entry.program_id,
                status=QueueEntryStatus.COMPLETE,
                last_stop_reason=stop.value,
            )
            result.notes.append(
                f"{entry.program_id}: COMPLETE -- terminal; it will never be "
                "dispatched again"
            )
            return

        kind = _DECISION_STOPS.get(stop)
        if kind is not None:
            self._route_to_decision_queue(entry, report, state_root, result, kind)

        if stop in _QUARANTINE_STOPS or kind is not None:
            update_entry(
                self.queue_root,
                entry.program_id,
                status=QueueEntryStatus.QUARANTINED,
                last_stop_reason=stop.value,
            )
            result.notes.append(
                f"{entry.program_id}: quarantined on {stop.value}; an operator "
                "decides, the dispatcher does not retry"
            )
            return

        # Everything else -- NO_ELIGIBLE_WORK, PAUSED, WAITING_ON_EXTERNAL_EVENT,
        # AWAITING_INDEPENDENT_VERIFICATION -- leaves the entry runnable. These
        # are conditions that can become false on their own, and a program that
        # is waiting for CI is not a program that needs a person.
        update_entry(
            self.queue_root,
            entry.program_id,
            status=QueueEntryStatus.PENDING,
            last_stop_reason=stop.value,
        )
        result.notes.append(
            f"{entry.program_id}: {stop.value}; still admitted and will be "
            "reconsidered when something changes"
        )


    def _route_to_decision_queue(
        self,
        entry: QueueEntry,
        report: SupervisorReport,
        state_root: Path,
        result: TickResult,
        kind: DecisionKind,
    ) -> None:
        """One durable question per blocker, then yield to a fallback.

        The blocking TASKS are identified rather than the program being blamed
        as a whole. A program-shaped question ("program X stopped") is one an
        operator cannot act on, and it also loses the per-task lease that has
        to be released and the per-task fallback that may run instead.

        A program-level question is still raised when no task can be named --
        a limit reached before anything was selected, for instance -- because
        an unanswerable silence is worse than a coarse question.
        """
        stop = report.stop_reason
        evidence = (
            f"stop_reason={stop.value}",
            f"launches_this_run={report.launches_this_run}",
            f"total_launches={report.launches}",
        )
        blocking = self._blocking_task_ids(state_root)
        handled = 0
        for task_id in blocking:
            envelope = load_envelope(state_root, task_id)
            if envelope is None:
                continue
            outcome = handle_blocked_task(
                state_root,
                envelope=envelope,
                kind=kind,
                subject=stop.value,
                question=(
                    f"Task {task_id} in program {entry.program_id} cannot "
                    f"proceed ({stop.value}). A person must decide; the "
                    "dispatcher has released its lease and will not ask again."
                ),
                requested_action=(
                    "Resolve the condition and re-admit the program, or record "
                    "an answer with `atlas program decisions --action answer`."
                ),
                worker_id=envelope.worker_id,
                session_id=self.session_id,
                evidence=evidence,
            )
            handled += 1
            if outcome.newly_raised:
                result.decisions_raised.append(outcome.decision.decision_id)
            freshness = (
                "new"
                if outcome.newly_raised
                else f"already open, seen {outcome.decision.seen_count}x"
            )
            result.notes.append(
                f"{task_id}: decision {outcome.decision.decision_id} "
                f"({freshness}); lease_released={outcome.lease_released} "
                f"({outcome.lease_release_detail}); "
                f"fallback={outcome.fallback_task_id} ({outcome.fallback_reason})"
            )
        if handled:
            return

        request, newly = raise_decision(
            state_root,
            program_id=entry.program_id,
            task_id=entry.program_id,
            kind=kind,
            subject=stop.value,
            question=(
                f"Program {entry.program_id} stopped with {stop.value} and no "
                "individual task could be named. A person must decide what "
                "happens next; the dispatcher will not retry it or ask again."
            ),
            requested_action=(
                "Inspect `atlas program status`, then either resolve the "
                "condition and re-admit the program, or record an answer with "
                "`atlas program decisions --action answer`."
            ),
            worker_id=f"dispatcher:{entry.program_id}",
            session_id=self.session_id,
            evidence=evidence,
        )
        if newly:
            result.decisions_raised.append(request.decision_id)
            result.notes.append(
                f"{entry.program_id}: one program-level decision recorded "
                f"({request.decision_id}); not re-asked"
            )
        else:
            result.notes.append(
                f"{entry.program_id}: decision {request.decision_id} is already "
                f"open (seen {request.seen_count}x); not re-asked"
            )

    @staticmethod
    def _blocking_task_ids(state_root: Path) -> tuple[str, ...]:
        """Tasks that are actually stuck, from durable state.

        BLOCKED is the state the DAG uses and the one that matters. A task
        merely waiting on an external event is deliberately excluded: waiting
        is not blocking, it resolves on its own, and asking an operator about
        it would be exactly the repeated question this layer refuses to ask.
        """
        state = load_state(state_root)
        if state is None:
            return ()
        return tuple(
            sorted(
                task_id
                for task_id, record in state.tasks.items()
                if record.state is NodeState.BLOCKED
            )
        )

    def _enrolled_for(self, loaded: LoadedProgram) -> tuple[Any, ...]:
        """Every ACTIVE enrolled agent whose role this program declares.

        Mirrors the finite path's resolution deliberately: binding is what makes
        enrolment govern a run at all -- the agent's identity becomes the
        principal on the lease, its narrowing applies, and its authority is
        re-read before every dispatch.

        A SUSPENDED or RETIRED agent is skipped rather than bound, because
        binding it and then refusing every dispatch reaches the same outcome
        noisily. An unreadable registry yields no agents, which leaves the
        supervisor to fail closed rather than run unbound.
        """
        if self.registry_root is None:
            return ()
        try:
            registry = load_registry(self.registry_root)
        except Exception:
            return ()
        roles = set(loaded.profiles.profiles)
        return tuple(
            agent
            for agent in sorted(
                registry.agents.values(), key=lambda item: item.agent_id
            )
            if agent.role in roles and agent.status is AgentStatus.ACTIVE
        )

    # ------------------------------------------------------------------ wait

    def wait(self, seconds: float) -> float:
        """Sleep in quanta, returning early on a wake. Returns time slept.

        The loop body is one ``stat``. It is not an ``inotify`` watch and does
        not claim to be; what it is, is bounded, portable and measurable, and
        the acceptance test measures the CPU it actually costs rather than
        taking this paragraph's word for it.
        """
        if seconds <= 0:
            return 0.0
        deadline = self._clock() + seconds
        slept = 0.0
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return slept
            if consume_wake(self.root):
                return slept
            quantum = min(self.wake_quantum_seconds, remaining)
            self._sleep(quantum)
            slept += quantum

    # ------------------------------------------------------------------- run

    def run(
        self,
        *,
        max_ticks: int | None = None,
        max_seconds: float | None = None,
        exit_when_drained: bool = False,
    ) -> DispatcherStopReason:
        """The resident loop. Publishes a terminal reason before it returns.

        ``max_ticks`` and ``max_seconds`` exist so this is testable and so an
        operator can run a bounded session; a service runs it with neither.
        ``exit_when_drained`` is off by default: a resident dispatcher whose
        queue empties is *waiting*, not finished, and exiting there would be
        the behaviour the whole module exists to replace.
        """
        clear_signals(self.root)
        self.publish(state=DispatcherState.STARTING)
        started = self._clock()
        reason = DispatcherStopReason.TICK_BUDGET_REACHED
        last_stop: str | None = None
        self._last_queue_status = "UNKNOWN"
        self._last_queue_error = None
        self._last_queue_error_code = None
        self._last_notes = []
        try:
            while True:
                if (dispatcher_dir(self.root) / STOP_NAME).is_file():
                    reason = DispatcherStopReason.OPERATOR_STOP
                    break
                if max_ticks is not None and self._ticks >= max_ticks:
                    reason = DispatcherStopReason.TICK_BUDGET_REACHED
                    break
                if max_seconds is not None and self._clock() - started >= max_seconds:
                    reason = DispatcherStopReason.DEADLINE_REACHED
                    break

                draining = (dispatcher_dir(self.root) / DRAIN_NAME).is_file()
                result = (
                    TickResult(tick=self._ticks, state=DispatcherState.DRAINING)
                    if draining
                    else self.tick()
                )
                if result.report is not None:
                    last_stop = result.report.stop_reason.value
                if result.queue_status != "UNKNOWN":
                    self._last_queue_status = result.queue_status
                    self._last_queue_error = result.queue_error
                    self._last_queue_error_code = result.queue_error_code
                if result.notes:
                    self._last_notes = list(result.notes)
                if result.queue_status == "UNREADABLE":
                    reason = DispatcherStopReason.QUEUE_UNREADABLE
                    break
                if draining:
                    reason = DispatcherStopReason.OPERATOR_DRAIN
                    break
                if exit_when_drained and result.state is DispatcherState.IDLE_EMPTY_QUEUE:
                    reason = DispatcherStopReason.QUEUE_DRAINED
                    break
                if result.launched == 0:
                    # D4: this used to key on the tick STATE, sleeping only for
                    # IDLE_EMPTY_QUEUE / PAUSED / WAITING_ON_WORK. A queue entry
                    # that stayed runnable while its program returned
                    # immediately -- NO_ELIGIBLE_WORK from a task stuck in
                    # OWNER_HELD, say -- reported RUNNING_PROGRAM and so never
                    # slept at all: measured 186 program runs in 5s against an
                    # expected 3, at 24% of one core, with the entry's run
                    # counter climbing into the thousands.
                    #
                    # The honest condition is not "what state did we report" but
                    # "did any work actually start". Launching nothing means
                    # there is nothing to come back for promptly, whatever the
                    # reason, so wait. Launching something means a worker is
                    # running and the next cycle should be timely.
                    result.slept_seconds = self.wait(self.tick_seconds)
        except Exception:
            self.publish(
                state=DispatcherState.STOPPED,
                last_stop=last_stop,
                terminal=DispatcherStopReason.FATAL_ERROR,
                queue_status=self._last_queue_status,
                queue_error=self._last_queue_error,
                queue_error_code=self._last_queue_error_code,
            )
            raise
        self.publish(
            state=DispatcherState.STOPPED,
            last_stop=last_stop,
            terminal=reason,
            queue_status=self._last_queue_status,
            queue_error=self._last_queue_error,
            queue_error_code=self._last_queue_error_code,
        )
        return reason


def dispatcher_status(root: Path) -> dict[str, Any]:
    """A machine-readable view of the resident dispatcher, for an operator.

    ``alive`` is three-valued in effect: ``True`` only when the recorded pid is
    running under the recorded start identity, ``False`` when it demonstrably
    is not, and ``None`` when nothing was recorded to check. Absence is not
    inferred from a gap in our own bookkeeping.
    """
    beat = read_heartbeat(root)
    if beat is None:
        return {
            "heartbeat": None,
            "alive": None,
            "detail": "no dispatcher heartbeat has ever been written here",
            "paused": pause_requested(root) is not None,
            "model_backed_dispatch": "DISABLED",
        }
    from project_atlas.orchestration.program.adapters.base import pid_is_alive

    alive: bool | None
    if not pid_is_alive(beat.pid):
        alive, detail = False, f"pid {beat.pid} is not running"
    else:
        live = process_start_identity(beat.pid)
        if not live or live == "unknown" or beat.process_start_identity == "unknown":
            alive, detail = (
                None,
                f"pid {beat.pid} is running but its start identity cannot be "
                "compared with the recorded one",
            )
        elif live == beat.process_start_identity:
            alive, detail = True, f"pid {beat.pid} is the recorded dispatcher"
        else:
            alive, detail = (
                False,
                f"pid {beat.pid} is running under a different start identity; "
                "the dispatcher exited and the pid was reused",
            )
    state = load_state(root)
    return {
        "heartbeat": beat.model_dump(mode="json"),
        "alive": alive,
        "detail": detail,
        "queue_status": beat.queue_status,
        "queue_error": beat.queue_error,
        "queue_error_code": beat.queue_error_code,
        "paused": pause_requested(root) is not None,
        "program_paused": bool(state.paused) if state is not None else None,
        "model_backed_dispatch": "DISABLED",
        "truth_boundary": TRUTH_BOUNDARY,
    }
