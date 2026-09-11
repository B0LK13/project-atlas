"""Durable program state: checkpoints written before the effects they name.

Two artifacts, deliberately separate:

  ``state.json``   the reconciled current picture -- task states, attempt
                   counters, launch counts, the supervisor identity that owns
                   the program. Rewritten atomically, always readable.

  ``events.jsonl`` an append-only log of every transition, in order. A
                   checkpoint that says "the adapter was invoked" and is never
                   followed by a terminal record is exactly how an interrupted
                   run is detected -- so the log is appended and flushed
                   BEFORE the effect it precedes, never after.

Neither is authority. Both are evidence. A worker cannot write either.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program.models import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    AttemptPhase,
    ExecutionConfidence,
    FailureClass,
    ProgramError,
    ProgramStopReason,
)

STATE_NAME: Final[str] = "state.json"
EVENTS_NAME: Final[str] = "events.jsonl"
EVIDENCE_DIR: Final[str] = "evidence"
#: One file per in-flight attempt, holding the pid and start identity of the
#: child the moment it exists. Deliberately NOT part of ``state.json``: it is
#: written by the worker thread, which never touches the state object, and it
#: has to survive a supervisor that is killed between checkpoints -- which is
#: exactly when it is needed.
LAUNCHES_DIR: Final[str] = "launches"
#: Program state lives beside, never inside, the workspace the workers mutate,
#: so a worker's own diff can never contain the supervisor's checkpoint.
DEFAULT_STATE_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "program"


class StoreError(ProgramError):
    code = "PROGRAM_STORE_ERROR"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AttemptRecord(BaseModel):
    """One attempt at one task: the durable trace of a single dispatch."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: str = Field(min_length=1, max_length=256)
    task_id: str = Field(min_length=1, max_length=128)
    attempt_number: int = Field(ge=1, le=10_000)
    idempotency_key: str = Field(min_length=1, max_length=256)
    profile_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    adapter: str = Field(min_length=1, max_length=64)
    #: Digest of the fully resolved effective profile. Two attempts with the
    #: same key but different digests are different work, and the key includes
    #: this so they can never be mistaken for a duplicate of one another.
    profile_digest: str = Field(min_length=64, max_length=64)
    base_pin: str = Field(min_length=40, max_length=40)
    lease_id: str | None = None
    phase: AttemptPhase = AttemptPhase.INTENT_RECORDED
    #: Runtime session identity, assigned by the supervisor BEFORE launch so an
    #: interrupted invocation is still addressable. ``None`` for adapters with
    #: no session concept.
    runtime_session_id: str | None = Field(default=None, max_length=256)
    process_pid: int | None = Field(default=None, ge=0, le=2**31 - 1)
    #: Guards against PID reuse: a live PID whose start identity differs is a
    #: different process, not our worker.
    process_start_identity: str | None = Field(default=None, max_length=256)
    started_at: str = Field(default_factory=_utc_now)
    ended_at: str | None = None
    exit_status: int | None = None
    confidence: ExecutionConfidence | None = None
    failure_class: FailureClass | None = None
    #: Worker's own claim about what it did. Recorded, never trusted.
    worker_reported: str | None = Field(default=None, max_length=8192)
    #: Whether every acceptance check the supervisor ran passed.
    acceptance_passed: bool | None = None
    acceptance_detail: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    #: Relative paths of evidence written under ``evidence/``.
    evidence_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    estimated_cost_usd: float | None = None
    #: Tool/permission requests the runtime denied. 0 means "not observed",
    #: never "definitely none" -- some runtimes cannot report denials.
    policy_denials: int = Field(default=0, ge=0, le=1_000_000)
    usage: dict[str, Any] = Field(default_factory=dict)
    notes: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    merge_authorized: Literal[False] = False
    #: Provenance copied from ProgramTask at DISPATCH_INTENT (B2). Optional;
    #: legacy attempts without these fields remain readable as UNKNOWN.
    contract_digest: str | None = Field(default=None, max_length=64)
    source_item_digest: str | None = Field(default=None, max_length=128)
    origination_identity: str | None = Field(default=None, max_length=64)


class TaskRecord(BaseModel):
    """Reconciled per-task state."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=128)
    state: NodeState = NodeState.DISCOVERED
    attempts: int = Field(default=0, ge=0, le=10_000)
    launches: int = Field(default=0, ge=0, le=10_000)
    last_attempt_id: str | None = None
    last_failure_class: FailureClass | None = None
    #: Observer id for an unresolved external precondition, if any.
    pending_observer_id: str | None = None
    #: Set when a task passed local acceptance but still needs a distinct
    #: agent to certify it. TASK_COMPLETE != PROGRAM_COMPLETE, and acceptance
    #: != independent verification.
    awaiting_independent_verification: bool = False
    verified_by_agent_id: str | None = None
    #: Fingerprint of the observable evidence at the end of the last attempt.
    #: Progress is "this changed", not "there were more messages".
    progress_fingerprint: str | None = None
    reason: str = Field(default="", max_length=512)


class HandoffRecord(BaseModel):
    """An operator explicitly enrolling an existing stored session.

    Neither supported runtime can attach to a *running* interactive session,
    and this package never adopts a process it did not start. What it does
    support is the controlled alternative: an operator names a session the
    runtime has stored, and the next dispatch for that task continues that
    conversation in a new supervised run instead of starting from nothing.

    The enrolment is a recorded human act -- ``enrolled_by`` and ``note`` say
    who asked and why. It is consumed exactly once: a handoff that fired and
    then sat around would resume the same session on a later attempt, which is
    a duplicate dispatch wearing a different name.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=128)
    adapter: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=256)
    enrolled_by: str = Field(min_length=1, max_length=256)
    enrolled_at: str = Field(default_factory=_utc_now)
    note: str = Field(default="", max_length=1024)
    consumed_by_attempt_id: str | None = None
    #: What the adapter's own probe said about this session at enrolment time.
    #: ``None`` means the adapter could not tell, which is recorded rather
    #: than smoothed over -- an operator enrolling an id the runtime has never
    #: heard of should be able to see that nothing corroborated it.
    session_observed: bool | None = None


class ProgramStateRecord(BaseModel):
    """The reconciled picture of one approved program."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-PROGRAM-SUPERVISOR-001"] = PACKAGE_ID
    truth_boundary: str = TRUTH_BOUNDARY
    program_id: str = Field(min_length=1, max_length=128)
    program_digest: str = Field(min_length=64, max_length=64)
    base_pin: str = Field(min_length=40, max_length=40)
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)
    #: Which supervisor instance most recently owned this program.
    supervisor_instance_id: str | None = None
    supervisor_pid: int | None = None
    total_launches: int = Field(default=0, ge=0, le=1_000_000)
    total_cycles: int = Field(default=0, ge=0, le=10_000_000)
    idle_cycles: int = Field(default=0, ge=0, le=1_000_000)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    cancel_requested: bool = False
    #: Stops NEW dispatch while leaving running workers alone. Reversible;
    #: cancellation is not.
    paused: bool = False
    paused_by: str | None = None
    paused_at: str | None = None
    complete: bool = False
    last_stop_reason: ProgramStopReason | None = None
    tasks: dict[str, TaskRecord] = Field(default_factory=dict)
    attempts: dict[str, AttemptRecord] = Field(default_factory=dict)
    #: Pending and spent session hand-offs, keyed by task id.
    handoffs: dict[str, HandoffRecord] = Field(default_factory=dict)
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def state_dir(root: Path) -> Path:
    """Program state directory for a supervisor root."""
    return root / DEFAULT_STATE_RELATIVE


def state_path(root: Path) -> Path:
    return state_dir(root) / STATE_NAME


def events_path(root: Path) -> Path:
    return state_dir(root) / EVENTS_NAME


def evidence_dir(root: Path) -> Path:
    return state_dir(root) / EVIDENCE_DIR


def launches_dir(root: Path) -> Path:
    return state_dir(root) / LAUNCHES_DIR


def _launch_name(attempt_id: str) -> str:
    """A filesystem-safe name for an attempt id, collision-free.

    Attempt ids contain dots and are otherwise tame, but they are built from a
    program id and a task id that a program file supplies, so the name is
    hashed rather than trusted. Truncating instead would let two attempts share
    a file, and a worker overwriting another worker's pid is worse than a long
    filename.
    """
    return hashlib.sha256(attempt_id.encode("utf-8")).hexdigest() + ".json"


def record_launch(
    root: Path, *, attempt_id: str, pid: int, start_identity: str
) -> Path:
    """Make one in-flight process identity durable, immediately.

    Called on the worker thread from the adapter's spawn site, so it touches no
    shared object: one attempt, one file, written atomically and fsynced before
    the adapter does anything else. The supervisor may be killed one
    instruction later and the identity still survives.
    """
    target = launches_dir(root) / _launch_name(attempt_id)
    _write_atomic(
        target,
        json.dumps(
            {
                "attempt_id": attempt_id,
                "pid": int(pid),
                "process_start_identity": start_identity,
                "recorded_at": _utc_now(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return target


def _launch_intent_name(attempt_id: str) -> str:
    return hashlib.sha256(attempt_id.encode("utf-8")).hexdigest() + ".intent.json"


def record_launch_intent(
    root: Path,
    *,
    attempt_id: str,
    pid: int,
    supervisor_pid: int,
    supervisor_instance_id: str | None,
    supervisor_start_identity: str | None,
) -> Path:
    """Record that a child EXISTS, the instant it exists, before asking who it is.

    The identity probe is not free. On Windows ``process_start_identity`` starts
    PowerShell, which takes long enough that a worker can finish starting,
    consult its own program's status, and be told no launch was ever recorded --
    because at that moment none had been. The record was written after the
    probe, not after the spawn. Measured: two independent Windows hosts lose
    that window 18 times out of 18, while a hosted runner wins it every time, so
    the exposure is a property of the machine and not of chance.

    Splitting the record in two is what removes the window. This file says "a
    process with this pid was launched for this attempt, and we have not yet
    established its start identity". It is written between ``Popen`` and the
    probe, so there is no instant at which a live child is unrecorded.

    The launcher's own identity travels with it, because that is what keeps
    the weaker record safe to act on. A pid alone cannot be told apart from a
    reused one, so this record names the supervisor that is waiting for the
    child -- and names it in a way that survives the supervisor dying.

    All three fields are needed, and the third is the one that is easy to think
    redundant. ``supervisor_instance_id`` is compared against ``state.json``,
    which is written by the supervisor and NEVER cleared on exit -- so after a
    SIGKILL it still holds the dead supervisor's token. A stranger that lands
    on the dead launcher's recycled pid would then be vouched for by a file the
    dead launcher wrote. ``supervisor_start_identity`` is what closes that: it
    is re-derived from the live pid at read time, and a stranger on that number
    has a different start time. It is the same trick B1 uses to defeat pid
    reuse for workers, applied to the launcher.

    Found by the clean-room gate against the first version of this record,
    which carried only the pid and the token.
    """
    target = launches_dir(root) / _launch_intent_name(attempt_id)
    _write_atomic(
        target,
        json.dumps(
            {
                "attempt_id": attempt_id,
                "pid": int(pid),
                "identity_state": "PENDING",
                "supervisor_pid": int(supervisor_pid),
                "supervisor_instance_id": supervisor_instance_id,
                "supervisor_start_identity": supervisor_start_identity,
                "recorded_at": _utc_now(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return target


def load_launch_intent(root: Path, attempt_id: str) -> dict[str, Any] | None:
    """The pre-identity launch record, or None when none was written.

    Same rule as ``load_launch``: None means "never recorded", never "gone".
    """
    path = launches_dir(root) / _launch_intent_name(attempt_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("attempt_id") != attempt_id:
        return None
    return raw


def load_launch(root: Path, attempt_id: str) -> dict[str, Any] | None:
    """The recorded in-flight identity, or None when none was ever written.

    None means "never recorded", which is NOT the same as "the process is
    gone". Callers must not collapse the two.
    """
    path = launches_dir(root) / _launch_name(attempt_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A torn or unreadable record is not evidence of absence either.
        return None
    if not isinstance(raw, dict) or raw.get("attempt_id") != attempt_id:
        return None
    return raw


def clear_launch(root: Path, attempt_id: str) -> None:
    """Drop the record once the attempt is terminal.

    Left behind, it would name a pid the operating system is free to reuse, and
    a later reader would have to decide whether a live stranger is our worker.
    The start identity would catch that, but not keeping the stale record is
    the cheaper answer.
    """
    for path in (
        launches_dir(root) / _launch_name(attempt_id),
        launches_dir(root) / _launch_intent_name(attempt_id),
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue


def _write_atomic(target: Path, text: str) -> None:
    """Write, fsync, then rename. A torn state file is not a state file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(str(tmp), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, target)


def load_state(root: Path) -> ProgramStateRecord | None:
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(
            f"program state at {path} is unreadable: {exc}",
            code="STATE_UNREADABLE",
        ) from exc
    return ProgramStateRecord.model_validate(raw)


def persist_state(root: Path, state: ProgramStateRecord) -> Path:
    state.updated_at = _utc_now()
    path = state_path(root)
    _write_atomic(path, json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return path


def append_event(root: Path, name: str, payload: dict[str, Any]) -> None:
    """Append one durable event and fsync it.

    fsync matters here and nowhere else in this module: this log is the only
    record that survives an abrupt kill between two state writes, and a
    checkpoint that is still sitting in the page cache when the machine dies
    is a checkpoint that was never taken.
    """
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": _utc_now(), "event": name, **payload}
    line = json.dumps(row, sort_keys=True, default=str) + "\n"
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read_events(root: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = events_path(root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # A partially written final line after a hard kill. Recorded
                # as a residue rather than discarded silently.
                rows.append({"event": "MALFORMED_EVENT_LINE", "raw_bytes": len(text)})
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    if limit is not None and limit >= 0:
        return rows[-limit:]
    return rows


def write_evidence(root: Path, relative_name: str, payload: dict[str, Any]) -> Path:
    """Write one evidence document under the program's evidence directory."""
    base = evidence_dir(root).resolve()
    target = (evidence_dir(root) / relative_name).resolve()
    if not target.is_relative_to(base):
        raise StoreError(
            "evidence path escapes the program evidence directory",
            code="EVIDENCE_PATH_ESCAPE",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(target, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return target
