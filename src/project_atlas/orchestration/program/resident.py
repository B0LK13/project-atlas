"""The resident dispatcher: a process that outlives every program.

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

The resident path does not decide whether provider execution is authorised:
queue admission, enrollment, the persisted envelope and the supervisor gates
do that. It only routes an admitted profile to the adapter already selected by
``ProgramSupervisor``. A provider profile therefore reaches the same normal
path, while an unsupported adapter still fails before launch.
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
    decisions_dir,
    raise_decision,
)
from project_atlas.orchestration.program.enrollment import AgentStatus, load_registry, registry_path
from project_atlas.orchestration.program.loader import (
    LoadedProgram,
    load_program,
)
from project_atlas.orchestration.program.models import ProgramError, ProgramStopReason
from project_atlas.orchestration.program.path_safety import (
    ContainmentError,
    check_children,
    checked_path,
    child_path,
    trusted_root,
)
from project_atlas.orchestration.program.profiles import AdapterKind
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
    model_calls: int = Field(default=0, ge=0, le=1_000_000)
    model_backed_dispatch: Literal["DISABLED", "ENABLED"] = "DISABLED"
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
    return child_path(state_dir(root), DISPATCHER_DIR)


def heartbeat_path(root: Path) -> Path:
    return child_path(dispatcher_dir(root), HEARTBEAT_NAME)


def read_heartbeat(root: Path) -> Heartbeat | None:
    path = heartbeat_path(root)
    if not path.is_file():
        return None
    import json

    try:
        raw = json.loads(checked_path(path, root=root).read_text(encoding="utf-8"))
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
    target = child_path(dispatcher_dir(root), WAKE_NAME)
    return write_json_atomic(target, {"at": utc_now(), "reason": reason})


def consume_wake(root: Path) -> bool:
    """Take the wake if one is pending. Once-only, like every other signal here."""
    target = child_path(dispatcher_dir(root), WAKE_NAME)
    if not target.is_file():
        return False
    try:
        checked_path(target, root=root).unlink()
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
    target = child_path(dispatcher_dir(root), PAUSE_NAME)
    if not target.is_file():
        return False
    checked_path(target, root=root).unlink()
    return True


def pause_requested(root: Path) -> dict[str, Any] | None:
    """The pause record, re-read from disk every tick. None when not paused."""
    target = child_path(dispatcher_dir(root), PAUSE_NAME)
    if not target.is_file():
        return None
    import json

    try:
        raw = json.loads(checked_path(target, root=root).read_text(encoding="utf-8"))
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
            child_path(dispatcher_dir(root), name).unlink(missing_ok=True)
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
    """A resident process above the finite program runner."""

    def __init__(
        self,
        *,
        root: Path,
        queue_root: Path,
        checkout: Path | None = None,
        registry_root: Path | None = None,
        governed_root: Path | None = None,
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
        self.governed_root = trusted_root(governed_root or root)
        self.root = checked_path(root, root=self.governed_root)
        self.queue_root = checked_path(queue_root, root=self.governed_root)
        self.checkout = (checkout or Path.cwd()).resolve()
        self.registry_root = trusted_root(registry_root) if registry_root is not None else None
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
                verify_entry(entry, governed_root=self.governed_root)
            except (QueueError, ContainmentError) as exc:
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
            queue = load_queue(self.queue_root, governed_root=self.governed_root)
        except (QueueError, ContainmentError) as exc:
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
        try:
            verify_entry(entry, governed_root=self.governed_root)
            state_root = checked_path(Path(entry.state_root), root=self.governed_root)
            loaded = load_program(Path(entry.program_path), governed_root=self.governed_root)
            if loaded.program.program_id != entry.program_id:
                raise QueueError("queue program id mismatch", code="QUEUE_PROGRAM_MISMATCH")
            profiles = (*loaded.effective.values(), *loaded.verifiers.values())
            self._heartbeat.model_backed_dispatch = (
                "ENABLED"
                if any(profile.adapter is not AdapterKind.LOCAL_COMMAND for profile in profiles)
                else "DISABLED"
            )
            enrolled = self._enrolled_for(loaded)
        except ProgramError as exc:
            result.state = DispatcherState.WAITING_ON_WORK
            result.queue_error = str(exc)
            result.queue_error_code = exc.code
            update_entry(
                self.queue_root,
                entry.program_id,
                governed_root=self.governed_root,
                status=QueueEntryStatus.QUARANTINED,
                last_stop_reason="PROGRAM_UNLOADABLE",
                note=str(exc),
            )
            result.notes.append(
                f"{entry.program_id}: quarantined -- "
                f"{getattr(exc, 'code', type(exc).__name__)}: {exc}"
            )
            return None

        check_children(decisions_dir(state_root), root=state_root)
        skip = blocked_task_ids(state_root)
        if skip:
            result.notes.append(
                f"{entry.program_id}: {len(skip)} task(s) have an open operator "
                "decision and will not be re-asked: " + ", ".join(sorted(skip))
            )

        # An envelope per approved task, BEFORE anything launches. A task with
        # no recorded authority is a task a replacement session cannot
        # reconstruct, and the moment to write it is before the work, not after.
        head, tree = _git_revision(checked_path(loaded.workspace, root=self.governed_root))
        from project_atlas.orchestration.program.candidate import (
            UNVERSIONED_FIXTURE_BOUNDARY,
            require_revision,
        )

        try:
            candidate_head, candidate_tree = require_revision(loaded, head, tree)
        except ProgramError as exc:
            update_entry(self.queue_root, entry.program_id, governed_root=self.governed_root,
                         status=QueueEntryStatus.QUARANTINED, note=f"{exc.code}: {exc}")
            result.notes.append(f"{exc.code}: {exc}")
            return None
        if not head or not tree:
            result.notes.append(UNVERSIONED_FIXTURE_BOUNDARY)

        # D5: the resident path threaded `registry_root` but never passed
        # `enrolled_agents`, so `_apply_enrollments` never ran, the program's
        # profiles kept their placeholder agent ids, and EVERY task was held
        # with "no active enrolled agent is bound" -- even with an ACTIVE,
        # correctly assigned agent in the registry. It failed closed, which is
        # safe, but a registry-configured deployment could never dispatch at
        # all. The finite `program start` path bound enrolments all along; only
        # this one did not, which is why no test caught it.
        supervisor = (
            self._supervisor_factory(loaded, state_root)
            if self._supervisor_factory is not None
            else ProgramSupervisor(
                loaded,
                state_root=state_root,
                enrolled_agents=enrolled,
                registry_root=self.registry_root,
                governed_root=self.governed_root,
            )
        )
        materialise_envelopes(
            supervisor.loaded if isinstance(supervisor, ProgramSupervisor) else loaded,
            state_root, candidate_head=candidate_head, candidate_tree=candidate_tree,
        )
        update_entry(
            self.queue_root,
            entry.program_id,
            governed_root=self.governed_root,
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
                "model_backed_dispatch": self._heartbeat.model_backed_dispatch,
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
                governed_root=self.governed_root,
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
                revision_observed=bool(head and tree),
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
                governed_root=self.governed_root,
                status=QueueEntryStatus.COMPLETE,
                last_stop_reason=stop.value,
            )
            result.notes.append(
                f"{entry.program_id}: COMPLETE -- terminal; it will never be "
                "dispatched again"
            )
            return

        kind = _DECISION_STOPS.get(stop)
        fallback_available = False
        if kind is not None:
            fallback_available = self._route_to_decision_queue(
                entry, report, state_root, result, kind
            )

        if fallback_available and stop not in {
            ProgramStopReason.RECONCILE_REQUIRED, ProgramStopReason.CANCELLED,
        }:
            update_entry(self.queue_root, entry.program_id, governed_root=self.governed_root,
                         status=QueueEntryStatus.PENDING, last_stop_reason=stop.value)
            result.notes.append(
                "blocked task remains held; approved fallback returns through normal gates"
            )
            return

        if stop in _QUARANTINE_STOPS or kind is not None:
            update_entry(
                self.queue_root,
                entry.program_id,
                governed_root=self.governed_root,
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
            governed_root=self.governed_root,
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
    ) -> bool:
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
        check_children(decisions_dir(state_root), root=state_root)
        blocking = self._blocking_task_ids(state_root)
        handled = 0
        fallback_available = False
        for task_id in blocking:
            envelope = load_envelope(state_root, task_id)
            if envelope is None:
                continue
            outcome = handle_blocked_task(
                state_root,
                envelope=envelope,
                kind=kind,
                subject="TASK_BLOCKED",
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
                lease_root=state_dir(state_root),
            )
            fallback_available |= outcome.fallback_task_id is not None
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
            return fallback_available

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
        return False

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
            checked_path(registry_path(self.registry_root), root=self.registry_root)
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
        """Own the resident root before clearing signals or publishing state."""
        from project_atlas.orchestration.program.process_lock import (
            ProcessLockError,
            exclusive_process_lock,
        )

        try:
            with (
                exclusive_process_lock(dispatcher_dir(self.root) / "resident.lock"),
                exclusive_process_lock(self.queue_root / "resident-queue.lock"),
            ):
                return self._run_owned(max_ticks=max_ticks, max_seconds=max_seconds,
                                       exit_when_drained=exit_when_drained)
        except ProcessLockError as exc:
            raise DispatcherError(str(exc), code="DISPATCHER_DOUBLE_START") from exc

    def _run_owned(
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
        "model_backed_dispatch": beat.model_backed_dispatch,
        "truth_boundary": TRUTH_BOUNDARY,
    }


# ------------------------------------------------------------------ restart
#
# ATLAS-OPERATOR-RECOVERY-FOLLOWUP-001. `restart` takes a witness before
# anything stops, and `restart-verify` judges the restart against it, per
# criterion. Every write below lands in `dispatcher_dir(root)` and nowhere else:
# never the approved-work queue, a checkpoint, an envelope or program state. The
# restart path must not be able to launder a state edit.

#: What recovery is judged against. Written before anything is stopped.
_RESTART_WITNESS_NAME: Final[str] = "restart-witness.json"
#: The last verdict, for the record. Evidence, never authority.
_RESTART_VERDICT_NAME: Final[str] = "restart-verdict.json"
#: Operator-written. The ONLY source of a start command for `--mode supervised`.
#: This package never writes it, never synthesizes one, and never guesses a
#: service-manager line in its absence.
_RESTART_COMMAND_NAME: Final[str] = "restart-command.json"

_RESTART_CRITERIA: Final[tuple[str, ...]] = (
    "service_and_candidate",
    "state_recovery",
    "pause_and_uncertain",
    "no_double_execution",
)
_RESTART_PASS: Final[str] = "PASS"
_RESTART_FAIL: Final[str] = "FAIL"
_RESTART_UNVERIFIABLE: Final[str] = "UNVERIFIABLE"
#: The worker id reconciliation is asked on behalf of. It only decides between
#: WORKER_STILL_RUNNING and LEASE_HELD_ELSEWHERE, neither of which is launchable.
_RESTART_WORKER_ID: Final[str] = "restart-verify"


class RestartInFlightCheckpoint(BaseModel):
    """One non-terminal checkpoint as it stood at the witness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1, le=1_000_000)
    last_completed_step: str | None = None
    self_digest: str | None = Field(default=None, max_length=64)


class RestartWitness(BaseModel):
    """What a restart will be judged against, captured before anything stops.

    Proposal §2 PRE fields, plus three the checks need to be COUNTED rather
    than read back: ``task_launches_before`` (per-task launch counts from
    ``state.json``, so C4 is a subtraction), ``in_flight_checkpoints`` (so C2
    can tell a recovered checkpoint from a re-derived one), and
    ``programs_started_before``.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    mode: Literal["delegate", "supervised"]
    dispatcher_session_id: str = Field(min_length=1, max_length=190)
    pid: int = Field(ge=0, le=2**31 - 1)
    process_start_identity: str = Field(min_length=1, max_length=256)
    #: ``True`` or ``False``. ``None`` never reaches a witness: PRE refuses it.
    alive_at_witness: bool
    revision_head: str = Field(default="", max_length=64)
    revision_tree: str = Field(default="", max_length=64)
    #: The dispatcher pause signal file. Distinct from ``program_paused``.
    paused: bool
    #: ``state.json``'s own pause flag, or None when no state was recorded.
    program_paused: bool | None = None
    current_program_id: str | None = None
    queue_status: str = "UNKNOWN"
    queue_error_code: str | None = Field(default=None, max_length=64)
    terminal_task_ids: tuple[str, ...] = ()
    reconcile_required_task_ids: tuple[str, ...] = ()
    launches_before: int = Field(ge=0, le=1_000_000)
    programs_started_before: int = Field(default=0, ge=0, le=1_000_000)
    task_launches_before: dict[str, int] = Field(default_factory=dict)
    in_flight_checkpoints: dict[str, RestartInFlightCheckpoint] = Field(
        default_factory=dict
    )
    queue_root: str | None = None
    witnessed_at: str = Field(default_factory=utc_now)
    model_backed_dispatch: Literal["DISABLED", "ENABLED"] = "DISABLED"


def _restart_witness_path(root: Path) -> Path:
    return checked_path(dispatcher_dir(root) / _RESTART_WITNESS_NAME, root=root)


def _restart_verdict_path(root: Path) -> Path:
    return checked_path(dispatcher_dir(root) / _RESTART_VERDICT_NAME, root=root)


def _restart_command_path(root: Path) -> Path:
    return checked_path(dispatcher_dir(root) / _RESTART_COMMAND_NAME, root=root)


def write_restart_witness(root: Path, witness: RestartWitness) -> Path:
    """Persist the witness atomically, through the one ``_write_atomic`` boundary."""
    return write_json_atomic(_restart_witness_path(root), witness.model_dump(mode="json"))


def read_restart_witness(root: Path) -> RestartWitness | None:
    """The witness, or ``None`` when none was written. Torn or invalid raises."""
    path = _restart_witness_path(root)
    if not path.is_file():
        return None
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatcherError(
            f"restart witness at {path} is unreadable: {exc}",
            code="RESTART_WITNESS_UNREADABLE",
        ) from exc
    return read_durable(
        RestartWitness,
        raw,
        path=path,
        error=DispatcherError,
        code="RESTART_WITNESS_SCHEMA_INVALID",
        what="restart witness",
    )


def _read_restart_command(root: Path) -> tuple[str, ...] | None:
    """The operator-declared start command, as argv, or ``None`` if undeclared.

    The file holds ``{"restart_command": [...argv...]}`` or
    ``{"restart_command": "one command line"}``. A string is split with
    ``shlex`` and run WITHOUT a shell: no expansion, no substitution, exactly the
    words the operator wrote. A present file that does not declare a usable
    command raises ``RESTART_COMMAND_INVALID`` rather than reading as absent --
    a broken declaration is not the same fact as no declaration.
    """
    path = _restart_command_path(root)
    if not path.is_file():
        return None
    import json
    import shlex

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatcherError(
            f"restart command declaration at {path} is unreadable: {exc}",
            code="RESTART_COMMAND_INVALID",
        ) from exc
    value = raw.get("restart_command") if isinstance(raw, dict) else None
    argv: list[str]
    if isinstance(value, str):
        try:
            argv = shlex.split(value)
        except ValueError as exc:
            raise DispatcherError(
                f"restart_command at {path} cannot be split into words: {exc}",
                code="RESTART_COMMAND_INVALID",
            ) from exc
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        argv = list(value)
    else:
        raise DispatcherError(
            f"{path} does not declare restart_command as a string or a list of "
            "strings",
            code="RESTART_COMMAND_INVALID",
        )
    if not argv or not argv[0]:
        raise DispatcherError(
            f"restart_command at {path} is empty", code="RESTART_COMMAND_INVALID"
        )
    return tuple(argv)


def _take_restart_witness(
    root: Path,
    *,
    mode: Literal["delegate", "supervised"],
    queue_root: Path | None,
    governed_root: Path | None = None,
) -> RestartWitness:
    """Build the witness from durable state. Read-only; raises on anything unusable.

    Refuses ``alive is None`` with ``RESTART_IDENTITY_UNVERIFIABLE``. Any durable
    record it cannot read -- a corrupt or version-skewed checkpoint, an
    unreadable ``state.json`` -- propagates as that record's own refusal: a
    witness with a hole in it is not something a restart can be judged against.
    """
    from project_atlas.orchestration.program.continuation import list_checkpoints
    from project_atlas.orchestration.program.reconciliation import (
        Disposition,
        reconcile_root,
    )

    status = dispatcher_status(root)
    alive = status.get("alive")
    beat = read_heartbeat(root)
    if alive is None or beat is None:
        raise DispatcherError(
            "the outgoing dispatcher's identity cannot be established "
            f"(alive={alive!r}: {status.get('detail')}); nothing was stopped, "
            "and alive=None is not a yes",
            code="RESTART_IDENTITY_UNVERIFIABLE",
        )
    # F-02: status False also means PID reuse, not just process exit. A
    # replacement must not be launched under that ambiguous ownership record.
    _validate_restart_identity(beat.pid, beat.process_start_identity)
    checkpoints = list_checkpoints(root)
    current = beat.current_program_id
    terminal = tuple(
        sorted(item.identity.task_id for item in checkpoints if item.terminal)
    )
    in_flight = {
        item.identity.task_id: RestartInFlightCheckpoint(
            program_id=item.program_id,
            sequence=item.sequence,
            last_completed_step=item.last_completed_step,
            self_digest=item.self_digest,
        )
        for item in checkpoints
        if not item.terminal and (current is None or item.program_id == current)
    }
    verdicts = reconcile_root(
        root, our_worker_id=_RESTART_WORKER_ID, queue_root=queue_root,
        governed_root=governed_root,
    )
    reconcile_required = tuple(
        sorted(
            item.task_id
            for item in verdicts
            if item.disposition is Disposition.RECONCILE_REQUIRED
        )
    )
    state = load_state(root)
    task_launches = {
        task_id: (
            state.tasks[task_id].launches
            if state is not None and task_id in state.tasks
            else 0
        )
        for task_id in terminal
    }
    return RestartWitness(
        mode=mode,
        dispatcher_session_id=beat.dispatcher_session_id,
        pid=beat.pid,
        process_start_identity=beat.process_start_identity,
        alive_at_witness=bool(alive),
        revision_head=beat.revision_head,
        revision_tree=beat.revision_tree,
        paused=pause_requested(root) is not None,
        program_paused=bool(state.paused) if state is not None else None,
        current_program_id=current,
        queue_status=beat.queue_status,
        queue_error_code=beat.queue_error_code,
        terminal_task_ids=terminal,
        reconcile_required_task_ids=reconcile_required,
        launches_before=beat.launches,
        programs_started_before=beat.programs_started,
        task_launches_before=task_launches,
        in_flight_checkpoints=in_flight,
        queue_root=str(queue_root) if queue_root is not None else None,
        model_backed_dispatch=beat.model_backed_dispatch,
    )


def _validate_restart_identity(pid: int, identity: str) -> None:
    """F-02: permit a proven exit or a matching process, never a live stranger."""
    from project_atlas.orchestration.program.adapters.base import pid_is_alive

    if not identity or identity == "unknown":
        raise DispatcherError(
            "restart requires a recorded process start identity",
            code="RESTART_IDENTITY_UNVERIFIABLE",
        )
    if pid_is_alive(pid):
        live = process_start_identity(pid)
        if not live or live == "unknown" or live != identity:
            raise DispatcherError(
                f"pid {pid} does not have the outgoing dispatcher's identity; "
                "restart refused without launch or process intervention",
                code="RESTART_IDENTITY_UNVERIFIABLE",
            )


def _validate_restart_witness_current(root: Path, witness: RestartWitness) -> None:
    """Do not drain or replace a dispatcher that appeared after PRE (F-02)."""
    beat = read_heartbeat(root)
    if beat is None or (
        beat.dispatcher_session_id, beat.pid, beat.process_start_identity
    ) != (witness.dispatcher_session_id, witness.pid, witness.process_start_identity):
        raise DispatcherError(
            "dispatcher identity changed after the restart witness",
            code="RESTART_IDENTITY_UNVERIFIABLE",
        )
    _validate_restart_identity(witness.pid, witness.process_start_identity)


def _step_index(steps: tuple[str, ...], step: str | None) -> int:
    """-1 for no step yet, -2 for a step the envelope does not know."""
    if step is None:
        return -1
    return steps.index(step) if step in steps else -2


def _criterion(failures: list[str], unknowns: list[str]) -> str:
    """FAIL outranks UNVERIFIABLE outranks PASS. Nothing is averaged."""
    if failures:
        return _RESTART_FAIL
    if unknowns:
        return _RESTART_UNVERIFIABLE
    return _RESTART_PASS


def _unverifiable_restart_verdict(reason: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """All four UNVERIFIABLE, each saying why. Used when there is no witness."""
    return (
        {name: _RESTART_UNVERIFIABLE for name in _RESTART_CRITERIA},
        {name: [reason] for name in _RESTART_CRITERIA},
    )


def _evaluate_restart(
    root: Path,
    witness: RestartWitness,
    *,
    queue_root: Path | None = None,
    governed_root: Path | None = None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Judge the current state against the witness: four independent codes.

    Read-only. Every criterion is computed on its own and a read that fails
    makes only the criteria that needed it UNVERIFIABLE -- never PASS. There is
    no aggregate: a caller exits zero only when all four are PASS.
    """
    from project_atlas.orchestration.program.continuation import (
        CheckpointError,
        load_checkpoint,
    )
    from project_atlas.orchestration.program.reconciliation import (
        Disposition,
        ReconciliationVerdict,
        reconcile_root,
    )

    evidence: dict[str, list[str]] = {name: [] for name in _RESTART_CRITERIA}
    effective_queue = queue_root or (
        Path(witness.queue_root) if witness.queue_root else None
    )

    # ---- shared reads, each failure recorded rather than raised
    status: dict[str, Any] | None
    beat: Heartbeat | None
    try:
        status = dispatcher_status(root)
        beat = read_heartbeat(root)
    except ContinuationError as exc:
        status, beat = None, None
        status_error = f"{getattr(exc, 'code', 'DISPATCHER_ERROR')}: {exc}"
    else:
        status_error = ""
    verdicts: dict[str, ReconciliationVerdict] | None
    try:
        verdicts = {
            item.task_id: item
            for item in reconcile_root(
                root, our_worker_id=_RESTART_WORKER_ID, queue_root=effective_queue,
                governed_root=governed_root,
            )
        }
        verdict_error = ""
    except ProgramError as exc:
        verdicts = None
        verdict_error = f"{getattr(exc, 'code', 'RECONCILIATION_ERROR')}: {exc}"
    state: Any
    try:
        state = load_state(root)
        state_error = ""
    except ProgramError as exc:
        state = None
        state_error = f"{getattr(exc, 'code', 'STATE_ERROR')}: {exc}"
    new_process = (
        beat is not None
        and beat.dispatcher_session_id != witness.dispatcher_session_id
        and (beat.pid, beat.process_start_identity)
        != (witness.pid, witness.process_start_identity)
    )

    # ---- C1: right service, right candidate
    fails: list[str] = []
    unknown: list[str] = []
    if status is None or beat is None:
        unknown.append(status_error or "no dispatcher heartbeat after the restart")
    else:
        if beat.dispatcher_session_id == witness.dispatcher_session_id:
            fails.append(
                "the heartbeat still carries the witnessed dispatcher_session_id; "
                "no new dispatcher has published"
            )
        elif (beat.pid, beat.process_start_identity) == (
            witness.pid,
            witness.process_start_identity,
        ):
            fails.append(
                "the heartbeat's pid and start identity are the witnessed "
                "process's; a new session id alone is not a new process"
            )
        if not (witness.revision_head and witness.revision_tree):
            unknown.append("the witness recorded no revision to compare against")
        elif not (beat.revision_head and beat.revision_tree):
            unknown.append("the new heartbeat publishes no revision")
        elif (beat.revision_head, beat.revision_tree) != (
            witness.revision_head,
            witness.revision_tree,
        ):
            fails.append(
                f"revision moved: witness {witness.revision_head}/"
                f"{witness.revision_tree}, now {beat.revision_head}/"
                f"{beat.revision_tree}"
            )
        alive = status.get("alive")
        if alive is True:
            evidence["service_and_candidate"].append(
                f"alive=True for pid {beat.pid}"
            )
        elif alive is False:
            fails.append(f"alive=False: {status.get('detail')}")
        else:
            unknown.append(f"alive={alive!r}: {status.get('detail')}")
    evidence["service_and_candidate"].extend([*fails, *unknown])
    c1 = _criterion(fails, unknown)

    # ---- C2: in-flight work recovered from its checkpoint, not re-derived
    fails, unknown = [], []
    if witness.current_program_id is not None and not witness.in_flight_checkpoints:
        unknown.append(
            f"program {witness.current_program_id} was in flight at the witness "
            "but no checkpoint recorded it, so recovery from a checkpoint cannot "
            "be shown"
        )
    for task_id, before in sorted(witness.in_flight_checkpoints.items()):
        try:
            after = load_checkpoint(root, task_id)
        except CheckpointError as exc:
            fails.append(
                f"{task_id}: checkpoint is now unusable "
                f"({getattr(exc, 'code', 'CHECKPOINT_INVALID')})"
            )
            continue
        if after is None:
            fails.append(f"{task_id}: the witnessed checkpoint no longer exists")
            continue
        if after.sequence < before.sequence:
            fails.append(
                f"{task_id}: checkpoint sequence went from {before.sequence} "
                f"back to {after.sequence}"
            )
        elif after.sequence == before.sequence and after.self_digest != before.self_digest:
            fails.append(
                f"{task_id}: checkpoint sequence {after.sequence} was rewritten "
                "with different content"
            )
        envelope = load_envelope(root, task_id)
        steps = envelope.checkpoint_policy.steps if envelope is not None else ()
        if steps and not after.terminal:
            before_index = _step_index(steps, before.last_completed_step)
            after_index = _step_index(steps, after.last_completed_step)
            if after_index == -2:
                fails.append(f"{task_id}: checkpoint names an unknown step")
            elif after_index < before_index:
                fails.append(
                    f"{task_id}: last_completed_step went from "
                    f"{before.last_completed_step} back to {after.last_completed_step}"
                )
        if verdicts is None:
            unknown.append(f"{task_id}: reconciliation unreadable ({verdict_error})")
            continue
        verdict = verdicts.get(task_id)
        if verdict is None:
            unknown.append(f"{task_id}: no envelope, so no reconciliation verdict")
            continue
        if verdict.disposition is Disposition.START_FRESH:
            fails.append(f"{task_id}: reconciliation would start it from nothing")
        if (
            verdict.disposition is Disposition.RESUME_AT_NEXT_STEP
            and before.last_completed_step is not None
            and steps
            and verdict.resume_step == steps[0]
        ):
            fails.append(f"{task_id}: resumes at the first step, not from its checkpoint")
        evidence["state_recovery"].append(
            f"{task_id}: sequence {before.sequence}->{after.sequence}, "
            f"last_completed_step {before.last_completed_step}->"
            f"{after.last_completed_step}, disposition {verdict.disposition.value}"
        )
    evidence["state_recovery"].extend([*fails, *unknown])
    c2 = _criterion(fails, unknown)

    # ---- C3: pause and UNCERTAIN survive
    fails, unknown = [], []
    if witness.paused:
        if pause_requested(root) is None:
            fails.append("the dispatcher pause present at the witness is gone")
        if beat is None or not new_process:
            unknown.append(
                "no new dispatcher heartbeat, so dispatch-while-paused cannot be counted"
            )
        elif beat.launches or beat.programs_started:
            fails.append(
                f"the restarted dispatcher dispatched while paused: "
                f"launches={beat.launches}, programs_started={beat.programs_started}"
            )
        else:
            evidence["pause_and_uncertain"].append(
                "paused before and after; restarted dispatcher launches=0, "
                "programs_started=0"
            )
    if witness.program_paused:
        if state_error:
            unknown.append(f"state.json unreadable ({state_error})")
        elif state is None:
            unknown.append("state.json paused at the witness is now absent")
        elif not state.paused:
            fails.append("state.json's program pause present at the witness is gone")
    for task_id in witness.reconcile_required_task_ids:
        if verdicts is None:
            unknown.append(f"{task_id}: reconciliation unreadable ({verdict_error})")
            continue
        verdict = verdicts.get(task_id)
        if verdict is None:
            fails.append(f"{task_id}: the quarantined task has no verdict any more")
        elif verdict.disposition is not Disposition.RECONCILE_REQUIRED:
            fails.append(
                f"{task_id}: quarantine cleared, now {verdict.disposition.value}"
            )
        elif verdict.launchable:
            fails.append(f"{task_id}: quarantined but launchable")
        else:
            evidence["pause_and_uncertain"].append(
                f"{task_id}: still RECONCILE_REQUIRED, launchable=False"
            )
    evidence["pause_and_uncertain"].extend([*fails, *unknown])
    c3 = _criterion(fails, unknown)

    # ---- C4: no double execution, counted
    fails, unknown = [], []
    for task_id in witness.terminal_task_ids:
        before_count = witness.task_launches_before.get(task_id)
        if before_count is None:
            unknown.append(f"{task_id}: no launch count was witnessed")
        elif state_error:
            unknown.append(f"{task_id}: state.json unreadable ({state_error})")
        elif state is None and before_count > 0:
            unknown.append(f"{task_id}: state.json that counted launches is gone")
        else:
            after_count = (
                state.tasks[task_id].launches
                if state is not None and task_id in state.tasks
                else 0
            )
            delta = after_count - before_count
            if delta != 0:
                fails.append(
                    f"{task_id}: launches {before_count}->{after_count} "
                    f"(delta {delta}) for a task with a terminal checkpoint"
                )
            else:
                evidence["no_double_execution"].append(
                    f"{task_id}: launches {before_count}->{after_count}, delta 0"
                )
        if verdicts is None:
            unknown.append(f"{task_id}: reconciliation unreadable ({verdict_error})")
            continue
        verdict = verdicts.get(task_id)
        if verdict is None:
            unknown.append(f"{task_id}: no envelope, so no reconciliation verdict")
        elif verdict.launchable or verdict.disposition not in (
            Disposition.ALREADY_COMPLETE,
            Disposition.HUMAN_DECISION_REQUIRED,
        ):
            fails.append(
                f"{task_id}: terminal at the witness, now "
                f"{verdict.disposition.value} launchable={verdict.launchable}"
            )
    evidence["no_double_execution"].extend([*fails, *unknown])
    c4 = _criterion(fails, unknown)

    return (
        {
            "service_and_candidate": c1,
            "state_recovery": c2,
            "pause_and_uncertain": c3,
            "no_double_execution": c4,
        },
        evidence,
    )


def _process_has_exited(pid: int, recorded_identity: str) -> bool:
    """True once ``pid`` no longer runs under ``recorded_identity``.

    Gone, reused by another process (a different start identity), or a zombie
    that has exited and waits only to be reaped. Never signals anything.
    """
    if not _pid_is_alive_host(pid):
        return True
    if os.name != "nt":
        try:
            raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            close = raw.rfind(")")
            if close >= 0 and raw[close + 1 :].split()[:1] in (["Z"], ["X"]):
                return True
        except OSError:
            pass
    live = process_start_identity(pid)
    return bool(live) and live != "unknown" and live != recorded_identity


def _pid_is_alive_host(pid: int) -> bool:
    from project_atlas.orchestration.program.adapters.base import pid_is_alive

    return pid_is_alive(pid)
