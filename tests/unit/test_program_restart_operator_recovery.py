"""ATLAS-OPERATOR-RECOVERY-FOLLOWUP-001: `restart` acts, and proves it acted.

T1-T10 of CHANGE-PROPOSAL-OPERATOR-RECOVERY-001 §5, in order. Every worker is a
labelled FIXTURE (``_program_fixture_worker.py``); model calls are zero and
MODEL_BACKED_DISPATCH stays DISABLED.

Process safety, honoured literally: a signal is only ever sent to a pid this
module started, and only after that pid's live start identity has been compared
with the identity recorded when it was started. Dispatchers are stopped through
their own stop file, not by a signal. Supervised restarts run an
operator-declared ``restart_command`` that launches a test-owned dispatcher,
bounded by ``--max-seconds``, never a service manager.

Assertions key on codes, verdict values and counts -- never on prose.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program import approved_queue, resident
from project_atlas.orchestration.program.adapters.base import (
    pid_is_alive,
    process_start_identity,
)
from project_atlas.orchestration.program.cli import _build_parser, dispatch_cli
from project_atlas.orchestration.program.continuation import (
    CheckpointPolicy,
    ContinuationCheckpoint,
    ExecutionIdentity,
    ExternalEffectReceipt,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    checkpoints_dir,
    persist_checkpoint,
    persist_envelope,
    seal_checkpoint,
    utc_now,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import AcceptanceCheck, AcceptanceKind
from project_atlas.orchestration.program.reconciliation import Disposition, reconcile_one
from project_atlas.orchestration.program.store import (
    load_state,
    persist_state,
    write_json_atomic,
)

CLI = "project_atlas.orchestration.program.cli"
REPO = Path(__file__).resolve().parents[2]
FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")
CRITERIA = (
    "service_and_candidate",
    "state_recovery",
    "pause_and_uncertain",
    "no_double_execution",
)
ALL_PASS = dict.fromkeys(CRITERIA, "PASS")
ALL_UNVERIFIABLE = dict.fromkeys(CRITERIA, "UNVERIFIABLE")
#: Proposal §2 PRE, verbatim.
PROPOSAL_WITNESS_FIELDS = frozenset(
    {
        "dispatcher_session_id",
        "pid",
        "process_start_identity",
        "revision_head",
        "revision_tree",
        "paused",
        "program_paused",
        "current_program_id",
        "queue_status",
        "queue_error_code",
        "terminal_task_ids",
        "reconcile_required_task_ids",
        "launches_before",
        "witnessed_at",
    }
)
WORKER = "fixture-worker-01"

_IDENTITY_SUPPORTED = os.name != "nt" and process_start_identity(os.getpid()) not in (
    "",
    "unknown",
)
needs_identity = pytest.mark.skipif(
    not _IDENTITY_SUPPORTED,
    reason="needs a POSIX host that reports a process start identity",
)


# ---------------------------------------------------------------- utilities


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)


def _wait(predicate: Callable[[], bool], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


@dataclass
class _Record:
    pid: int
    identity: str
    kind: str  # "dispatcher" (stopped by its stop file) or "sleeper"
    stop_root: Path | None


class _Owned:
    """Every process this test started, by pid AND start identity."""

    def __init__(self) -> None:
        self.records: list[_Record] = []

    def adopt(
        self, pid: int, identity: str, *, kind: str, stop_root: Path | None = None
    ) -> None:
        assert identity and identity != "unknown", (
            f"pid {pid} has no start identity, so it cannot be owned"
        )
        self.records.append(_Record(pid, identity, kind, stop_root))

    def spawn(
        self, argv: list[str], *, kind: str, stop_root: Path | None = None
    ) -> subprocess.Popen[bytes]:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.adopt(proc.pid, process_start_identity(proc.pid), kind=kind, stop_root=stop_root)
        # Reap it, so an exited child is not a zombie that still answers kill(0).
        threading.Thread(target=proc.wait, daemon=True).start()
        return proc

    def sleeper(self) -> subprocess.Popen[bytes]:
        return self.spawn(
            [sys.executable, "-c", "import time; time.sleep(120)"], kind="sleeper"
        )

    def identity_of(self, pid: int) -> str:
        return next(r.identity for r in self.records if r.pid == pid)

    def cleanup(self) -> None:
        for record in self.records:
            if record.kind == "dispatcher" and record.stop_root is not None:
                resident.request_stop(record.stop_root, requested_by="test-cleanup")
                resident.request_wake(record.stop_root, reason="test-cleanup")
        for record in self.records:
            bound = 30.0 if record.kind == "dispatcher" else 0.0
            if _wait(
                lambda r=record: resident._process_has_exited(r.pid, r.identity),
                bound,
            ):
                continue
            # Only a pid whose LIVE start identity is the one recorded at start.
            if process_start_identity(record.pid) == record.identity:
                os.kill(record.pid, signal.SIGKILL)


@pytest.fixture
def owned() -> Iterator[_Owned]:
    registry = _Owned()
    try:
        yield registry
    finally:
        registry.cleanup()


def _cli(*args: str) -> tuple[dict[str, Any], int]:
    """The CLI in a fresh interpreter: its JSON object and its exit status."""
    completed = subprocess.run(
        [sys.executable, "-m", CLI, *args],
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert completed.stdout, completed.stderr
    payload: dict[str, Any] = json.loads(completed.stdout)
    return payload, completed.returncode


def _in_process(*args: str) -> tuple[dict[str, Any], int]:
    return dispatch_cli(_build_parser().parse_args(list(args)))


def _snapshot(root: Path, *, skip_dispatcher: bool = False) -> dict[str, str]:
    if not root.exists():
        return {}
    marker = resident.dispatcher_dir(root)
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if skip_dispatcher and path.is_relative_to(marker):
            continue
        found[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _profile() -> dict[str, Any]:
    return {
        "agent_id": "agent-one",
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "env_allowlist": [
            "ATLAS_FIXTURE_MODE",
            "ATLAS_PROGRAM_ATTEMPT",
            "ATLAS_PROGRAM_TASK",
        ],
        "adapter_options": {"argv": [sys.executable, str(FIXTURE_WORKER)]},
    }


def _program(tmp_path: Path, name: str, task_ids: list[str]) -> Path:
    workspace = tmp_path / f"{name}-ws"
    workspace.mkdir()
    tasks = [
        {
            "task_id": task_id,
            "title": f"task {task_id}",
            "instruction": "do it",
            "profile_ref": "impl",
            "mutation_paths": [f"{task_id}.txt"],
            "surface_id": task_id,
            "surface_semantic": task_id.upper().replace("-", "_"),
            "capabilities_required": ["IMPLEMENT"],
            "acceptance": [
                {
                    "check_id": f"{task_id}-out",
                    "kind": "FILE_EXISTS",
                    "description": f"{task_id}.txt exists",
                    "path": f"{task_id}.txt",
                }
            ],
        }
        for task_id in task_ids
    ]
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": name,
            "objective": "operator recovery coverage",
            "approved_by": "fixture-operator",
            "approval_reference": "tests/unit/test_program_restart_operator_recovery.py",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {
                "max_cycles": 20,
                "idle_sleep_seconds": 0.0,
                "max_concurrent_workers": 1,
                "max_attempts_per_task": 2,
            },
            "tasks": tasks,
        },
        "profiles": {"impl": _profile()},
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _admit(queue_root: Path, program: Path, state_root: Path) -> None:
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id=load_program(program).program.program_id,
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="operator recovery test",
    )


def _dispatcher_argv(
    root: Path, queue: Path, *, checkout: Path = REPO, max_seconds: float = 120.0
) -> list[str]:
    return [
        sys.executable,
        "-m",
        CLI,
        "program",
        "dispatcher",
        "--state-root",
        str(root),
        "--queue-root",
        str(queue),
        "--checkout",
        str(checkout),
        "--action",
        "run",
        "--tick-seconds",
        "0.5",
        "--max-seconds",
        str(max_seconds),
    ]


def _declare(root: Path, argv: list[str]) -> None:
    """What an operator does: write the one command supervised mode may run."""
    write_json_atomic(resident._restart_command_path(root), {"restart_command": argv})


def _write_heartbeat(
    root: Path, *, pid: int, identity: str, head: str = "", tree: str = ""
) -> None:
    beat = resident.Heartbeat(
        dispatcher_session_id="dispatcher.outgoing.fixture",
        pid=pid,
        process_start_identity=identity,
        revision_head=head,
        revision_tree=tree,
        started_at=utc_now(),
    )
    write_json_atomic(resident.heartbeat_path(root), beat.model_dump(mode="json"))


def _other_git_checkout(tmp_path: Path) -> Path:
    other = tmp_path / "other-candidate"
    other.mkdir()
    base = ["git", "-C", str(other), "-c", "user.name=fixture", "-c", "user.email=fixture@invalid"]
    subprocess.run([*base, "init", "-q"], check=True, capture_output=True)
    subprocess.run(
        [*base, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "other"],
        check=True,
        capture_output=True,
    )
    return other


def _quarantined_task(root: Path, task_id: str) -> None:
    """An UNCERTAIN_EXTERNAL_EFFECT task whose last effect nobody established."""
    envelope = _envelope(task_id, replay=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT)
    persist_envelope(root, envelope)
    checkpoint = _checkpoint(envelope, sequence=1)
    checkpoint.external_effects = (
        ExternalEffectReceipt(
            receipt_id=f"{task_id}-effect",
            kind="OUTBOUND_WRITE",
            description="outcome never established",
            recorded_at=utc_now(),
            confirmed=None,
        ),
    )
    persist_checkpoint(root, checkpoint)


def _envelope(
    task_id: str, *, replay: ReplayClass, steps: tuple[str, ...] = ()
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        objective=f"fixture task {task_id}",
        capabilities_required=("IMPLEMENT",),
        candidate_head="a" * 40,
        candidate_tree="b" * 40,
        allowed_paths=(f"{task_id}.txt",),
        acceptance=(
            AcceptanceCheck(
                check_id=f"{task_id}-out",
                kind=AcceptanceKind.FILE_EXISTS,
                description=f"{task_id}.txt exists",
                path=f"{task_id}.txt",
            ),
        ),
        budgets=TaskBudgets(),
        checkpoint_policy=CheckpointPolicy(steps=steps),
        replay_class=replay,
        approved_by="fixture-operator",
        approval_reference="tests/unit/test_program_restart_operator_recovery.py",
        profile_ref="impl",
        worker_id=WORKER,
        program_id="fixture-program",
    )


def _checkpoint(
    envelope: TaskEnvelope,
    *,
    sequence: int,
    last_step: str | None = None,
    terminal: bool = False,
) -> ContinuationCheckpoint:
    return ContinuationCheckpoint(
        identity=ExecutionIdentity(
            task_id=envelope.task_id,
            worker_id=envelope.worker_id,
            session_id=f"session.{sequence}",
            attempt_id=f"{envelope.task_id}.attempt.{sequence}",
        ),
        envelope_digest=envelope.digest(),
        program_id=envelope.program_id,
        sequence=sequence,
        last_completed_step=last_step,
        next_action=f"continue {envelope.task_id}",
        worktree_path="/fixture/worktree",
        git_head=envelope.candidate_head,
        git_tree=envelope.candidate_tree,
        replay_class=ReplayClass.COMPLETED if terminal else envelope.replay_class,
        terminal=terminal,
    )


def _checkpoint_file(root: Path, task_id: str) -> Path:
    name = hashlib.sha256(task_id.encode("utf-8")).hexdigest() + ".checkpoint.json"
    return checkpoints_dir(root) / name


@dataclass
class _Live:
    root: Path
    queue: Path
    old_pid: int
    old_identity: str
    old_session: str


def _start_live(tmp_path: Path, owned: _Owned) -> _Live:
    """A real resident dispatcher that has completed one program and is idle."""
    root = tmp_path / "state"
    queue = tmp_path / "queue"
    queue.mkdir()
    _admit(queue, _program(tmp_path, "restart-program", ["live-done"]), root)
    proc = owned.spawn(_dispatcher_argv(root, queue), kind="dispatcher", stop_root=root)

    def _settled() -> bool:
        try:
            beat = resident.read_heartbeat(root)
        except resident.DispatcherError:
            return False
        return (
            beat is not None
            and beat.pid == proc.pid
            and beat.programs_started == 1
            and beat.state is resident.DispatcherState.IDLE_EMPTY_QUEUE
        )

    assert _wait(_settled, 90), resident.read_heartbeat(root)
    assert resident.dispatcher_status(root)["alive"] is True
    beat = resident.read_heartbeat(root)
    assert beat is not None and beat.launches == 1
    return _Live(root, queue, proc.pid, owned.identity_of(proc.pid), beat.dispatcher_session_id)


def _supervised_restart(live: _Live, owned: _Owned) -> tuple[dict[str, Any], int]:
    payload, code = _cli(
        "program",
        "dispatcher",
        "--state-root",
        str(live.root),
        "--queue-root",
        str(live.queue),
        "--action",
        "restart",
        "--mode",
        "supervised",
        "--wait-seconds",
        "60",
    )
    start = payload.get("start")
    if isinstance(start, dict) and start.get("pid"):
        owned.adopt(
            int(start["pid"]),
            str(start["process_start_identity"]),
            kind="dispatcher",
            stop_root=live.root,
        )
    return payload, code


# =============================================================== T1


@needs_identity
def test_T1_identity_unverifiable_refuses_and_stops_nothing(
    tmp_path: Path, owned: _Owned
) -> None:
    root = tmp_path / "state"
    running = owned.sleeper()
    # A live pid whose start identity was never recorded: alive is None.
    _write_heartbeat(root, pid=running.pid, identity="unknown")
    assert resident.dispatcher_status(root)["alive"] is None
    marker = tmp_path / "started.marker"
    _declare(root, [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])
    before = _snapshot(root)

    for mode in ("delegate", "supervised"):
        payload, code = _cli(
            "program", "dispatcher", "--state-root", str(root),
            "--action", "restart", "--mode", mode,
        )
        assert payload["code"] == "RESTART_IDENTITY_UNVERIFIABLE", (mode, payload)
        assert code != 0
        assert payload["performed"] is False
        assert payload["stopped"] is False
        assert "restart_verdict" not in payload

    # Nothing stopped, nothing started, nothing written: no witness, no drain.
    assert _snapshot(root) == before
    assert not marker.exists()
    assert pid_is_alive(running.pid)
    assert process_start_identity(running.pid) == owned.identity_of(running.pid)

    # And with no heartbeat ever written.
    empty = tmp_path / "never-ran"
    payload, code = _cli(
        "program", "dispatcher", "--state-root", str(empty), "--action", "restart"
    )
    assert payload["code"] == "RESTART_IDENTITY_UNVERIFIABLE"
    assert code != 0
    assert not resident._restart_witness_path(empty).exists()


# =============================================================== T2


@needs_identity
def test_T2_supervised_without_a_declared_restart_command_refuses_without_fallback(
    tmp_path: Path, owned: _Owned
) -> None:
    root = tmp_path / "state"
    running = owned.sleeper()
    _write_heartbeat(root, pid=running.pid, identity=owned.identity_of(running.pid))
    assert resident.dispatcher_status(root)["alive"] is True
    before = _snapshot(root)

    payload, code = _cli(
        "program", "dispatcher", "--state-root", str(root),
        "--action", "restart", "--mode", "supervised",
    )
    assert payload["code"] == "RESTART_COMMAND_NOT_DECLARED", payload
    assert code != 0
    assert payload["performed"] is False
    assert payload["stopped"] is False and payload["started"] is False
    # No drain, no witness, no guessed command: the state root is byte-identical.
    assert _snapshot(root) == before
    assert pid_is_alive(running.pid)
    assert process_start_identity(running.pid) == owned.identity_of(running.pid)

    # The declaration is checked before any process is looked at, so it holds
    # even when identity is also unverifiable.
    unknown_root = tmp_path / "unknown"
    _write_heartbeat(unknown_root, pid=running.pid, identity="unknown")
    payload, code = _cli(
        "program", "dispatcher", "--state-root", str(unknown_root),
        "--action", "restart", "--mode", "supervised",
    )
    assert payload["code"] == "RESTART_COMMAND_NOT_DECLARED"
    assert code != 0

    # A declaration that is present but unusable is not an absent one.
    write_json_atomic(resident._restart_command_path(root), {"restart_command": 42})
    before_invalid = _snapshot(root)
    payload, code = _cli(
        "program", "dispatcher", "--state-root", str(root),
        "--action", "restart", "--mode", "supervised",
    )
    assert payload["code"] == "RESTART_COMMAND_INVALID"
    assert code != 0
    assert _snapshot(root) == before_invalid


# =============================================================== T3


@needs_identity
def test_T3_happy_path_same_pinned_revision_all_four_PASS(
    tmp_path: Path, owned: _Owned
) -> None:
    live = _start_live(tmp_path, owned)
    _declare(live.root, _dispatcher_argv(live.root, live.queue))

    payload, code = _supervised_restart(live, owned)
    assert payload["restart_verdict"] == ALL_PASS, payload.get("evidence", payload)
    assert code == 0
    assert "ok" not in payload
    assert payload["stop"]["drain_requested"] is True
    assert payload["stop"]["exited"] is True
    assert payload["stop"]["signal_sent"] is False
    assert resident._process_has_exited(live.old_pid, live.old_identity)

    new = resident.read_heartbeat(live.root)
    assert new is not None
    assert new.dispatcher_session_id != live.old_session
    assert new.pid == payload["start"]["pid"] != live.old_pid
    head, tree = resident._git_revision(REPO)
    assert (new.revision_head, new.revision_tree) == (head, tree)

    witness = json.loads(resident._restart_witness_path(live.root).read_text("utf-8"))
    assert set(witness) >= PROPOSAL_WITNESS_FIELDS
    assert witness["dispatcher_session_id"] == live.old_session
    assert witness["pid"] == live.old_pid
    recorded = json.loads(resident._restart_verdict_path(live.root).read_text("utf-8"))
    assert recorded["restart_verdict"] == ALL_PASS

    again, again_code = _cli(
        "program", "dispatcher", "--state-root", str(live.root),
        "--queue-root", str(live.queue), "--action", "restart-verify",
    )
    assert again["restart_verdict"] == ALL_PASS, again["evidence"]
    assert again_code == 0
    assert "ok" not in again


# =============================================================== T4


@needs_identity
def test_T4_revision_moved_between_stop_and_start_fails_service_and_candidate(
    tmp_path: Path, owned: _Owned
) -> None:
    live = _start_live(tmp_path, owned)
    other = _other_git_checkout(tmp_path)
    _declare(live.root, _dispatcher_argv(live.root, live.queue, checkout=other))

    payload, code = _supervised_restart(live, owned)
    verdict = payload["restart_verdict"]
    assert verdict["service_and_candidate"] == "FAIL", payload["evidence"]
    assert code != 0
    # Only the candidate moved, so only that criterion may fail.
    assert {k for k, v in verdict.items() if v != "PASS"} == {"service_and_candidate"}


# =============================================================== T5


@needs_identity
def test_T5_a_pid_reused_by_an_unrelated_process_is_not_mistaken_for_the_dispatcher(
    tmp_path: Path, owned: _Owned
) -> None:
    root = tmp_path / "state"
    queue = tmp_path / "queue"
    queue.mkdir()
    stranger = owned.sleeper()
    head, tree = resident._git_revision(REPO)
    # The recorded dispatcher's pid is now held by a stranger with another start.
    _write_heartbeat(
        root, pid=stranger.pid, identity="linux:0-not-this-process", head=head, tree=tree
    )
    assert pid_is_alive(stranger.pid)
    assert resident.dispatcher_status(root)["alive"] is False
    _declare(root, _dispatcher_argv(root, queue))

    payload, code = _supervised_restart(
        _Live(root, queue, stranger.pid, "linux:0-not-this-process", "dispatcher.outgoing.fixture"),
        owned,
    )
    assert payload["stop"]["alive_at_witness"] is False
    assert payload["stop"]["drain_requested"] is False
    assert payload["stop"]["signal_sent"] is False
    # The stranger was neither waited on as the dispatcher nor touched.
    assert pid_is_alive(stranger.pid)
    assert process_start_identity(stranger.pid) == owned.identity_of(stranger.pid)
    assert payload["restart_verdict"] == ALL_PASS, payload["evidence"]
    assert code == 0


# =============================================================== T6


@needs_identity
def test_T6_a_pause_survives_restart_and_nothing_is_dispatched_while_paused(
    tmp_path: Path, owned: _Owned
) -> None:
    live = _start_live(tmp_path, owned)
    resident.request_pause(live.root, requested_by="operator:test")

    def _paused() -> bool:
        beat = resident.read_heartbeat(live.root)
        return beat is not None and beat.state is resident.DispatcherState.PAUSED

    assert _wait(_paused, 30)
    # Work that WOULD run, admitted while paused, in its own state root.
    held = _program(tmp_path, "held-program", ["held-one"])
    _admit(live.queue, held, tmp_path / "held-state")
    _declare(live.root, _dispatcher_argv(live.root, live.queue))

    payload, code = _supervised_restart(live, owned)
    assert payload["restart_verdict"]["pause_and_uncertain"] == "PASS", payload["evidence"]
    assert payload["restart_verdict"] == ALL_PASS, payload["evidence"]
    assert code == 0
    new = resident.read_heartbeat(live.root)
    assert new is not None and new.paused is True
    assert new.launches == 0 and new.programs_started == 0
    assert resident.pause_requested(live.root) is not None
    assert not (tmp_path / "held-program-ws" / "held-one.txt").exists()

    # Positive control: the zero was not vacuous. Lift the pause and the same
    # restarted dispatcher launches the held work.
    resident.clear_pause(live.root)
    resident.request_wake(live.root, reason="positive control")

    def _launched() -> bool:
        beat = resident.read_heartbeat(live.root)
        return beat is not None and beat.launches >= 1

    assert _wait(_launched, 90), resident.read_heartbeat(live.root)
    assert (tmp_path / "held-program-ws" / "held-one.txt").exists()


# =============================================================== T7


@needs_identity
def test_T7_an_UNCERTAIN_quarantine_survives_restart_and_stays_unlaunchable(
    tmp_path: Path, owned: _Owned
) -> None:
    live = _start_live(tmp_path, owned)
    _quarantined_task(live.root, "unc-task")
    before = reconcile_one(live.root, "unc-task", our_worker_id=WORKER)
    assert before.disposition is Disposition.RECONCILE_REQUIRED
    assert before.launchable is False
    _declare(live.root, _dispatcher_argv(live.root, live.queue))

    payload, code = _supervised_restart(live, owned)
    witness = json.loads(resident._restart_witness_path(live.root).read_text("utf-8"))
    assert witness["reconcile_required_task_ids"] == ["unc-task"]
    assert payload["restart_verdict"] == ALL_PASS, payload["evidence"]
    assert code == 0

    reconciled, _ = _cli(
        "program", "continuation", "--state-root", str(live.root),
        "--action", "reconcile", "--worker-id", WORKER,
    )
    row = {r["task_id"]: r for r in reconciled["verdicts"]}["unc-task"]
    assert row["disposition"] == Disposition.RECONCILE_REQUIRED.value
    assert row["launchable"] is False


# =============================================================== T8


@needs_identity
def test_T8_a_completed_task_is_launched_zero_times_after_restart_counted(
    tmp_path: Path, owned: _Owned
) -> None:
    live = _start_live(tmp_path, owned)
    state = load_state(live.root)
    assert state is not None
    launches_before = state.tasks["live-done"].launches
    total_before = state.total_launches
    assert launches_before == 1, "the task must really have run once"
    _declare(live.root, _dispatcher_argv(live.root, live.queue))

    payload, code = _supervised_restart(live, owned)
    witness = json.loads(resident._restart_witness_path(live.root).read_text("utf-8"))
    assert "live-done" in witness["terminal_task_ids"]
    assert witness["task_launches_before"]["live-done"] == 1

    # Give the restarted dispatcher several ticks in which it COULD relaunch.
    def _ticked() -> bool:
        beat = resident.read_heartbeat(live.root)
        return beat is not None and beat.pid == payload["start"]["pid"] and beat.ticks >= 4

    assert _wait(_ticked, 60)
    after = load_state(live.root)
    assert after is not None
    assert after.tasks["live-done"].launches - launches_before == 0
    assert after.total_launches == total_before
    new = resident.read_heartbeat(live.root)
    assert new is not None and new.launches == 0
    verdict = reconcile_one(live.root, "live-done", our_worker_id=WORKER)
    assert verdict.disposition is Disposition.ALREADY_COMPLETE
    assert verdict.launchable is False
    assert payload["restart_verdict"]["no_double_execution"] == "PASS", payload["evidence"]
    assert code == 0

    again, again_code = _cli(
        "program", "dispatcher", "--state-root", str(live.root),
        "--queue-root", str(live.queue), "--action", "restart-verify",
    )
    assert again["restart_verdict"] == ALL_PASS, again["evidence"]
    assert again_code == 0


# =============================================================== T9


def test_T9_restart_verify_without_a_usable_witness_is_UNVERIFIABLE_never_PASS(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    payload, code = _cli(
        "program", "dispatcher", "--state-root", str(root), "--action", "restart-verify"
    )
    assert payload["restart_verdict"] == ALL_UNVERIFIABLE
    assert code != 0

    path = resident._restart_witness_path(root)
    for torn in ('{"schema_version": 1, "dispatcher_sess', json.dumps({"schema_version": 1})):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(torn, encoding="utf-8")
        payload, code = _cli(
            "program", "dispatcher", "--state-root", str(root), "--action", "restart-verify"
        )
        assert payload["restart_verdict"] == ALL_UNVERIFIABLE, torn
        assert code != 0


@needs_identity
def test_T9_an_interrupted_witness_write_starts_nothing_and_leaves_no_stale_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "state"
    queue = tmp_path / "queue"
    queue.mkdir()
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait(timeout=60)
    head, tree = resident._git_revision(REPO)
    _write_heartbeat(root, pid=gone.pid, identity="linux:0-exited", head=head, tree=tree)
    assert resident.dispatcher_status(root)["alive"] is False
    marker = tmp_path / "started.marker"
    _declare(root, [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])

    # A witness from an earlier restart is on disk.
    _, first = _in_process(
        "program", "dispatcher", "--state-root", str(root), "--action", "restart"
    )
    assert first == 0
    assert resident._restart_witness_path(root).is_file()

    real_replace = os.replace

    def _interrupted(src: Any, dst: Any) -> None:
        if Path(dst).name == resident._RESTART_WITNESS_NAME:
            raise OSError("injected: interrupted before the rename")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _interrupted)
    payload, code = _in_process(
        "program", "dispatcher", "--state-root", str(root), "--queue-root", str(queue),
        "--action", "restart", "--mode", "supervised", "--wait-seconds", "5",
    )
    monkeypatch.undo()
    assert payload["code"] == "STATE_WRITE_FAILED", payload
    assert code != 0
    assert not resident._restart_witness_path(root).exists(), "a stale witness survived"
    time.sleep(1.0)
    assert not marker.exists(), "something was started after the witness failed"

    verify, verify_code = _in_process(
        "program", "dispatcher", "--state-root", str(root), "--action", "restart-verify"
    )
    assert verify["restart_verdict"] == ALL_UNVERIFIABLE
    assert verify_code != 0


# =============================================================== T10


def _t10_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """A state root in which every criterion has something real to judge."""
    root = tmp_path / "state"
    queue = tmp_path / "queue"
    queue.mkdir()
    _admit(queue, _program(tmp_path, "gate-program", ["gate-done"]), root)
    run, code = _cli(
        "program", "dispatcher", "--state-root", str(root), "--queue-root", str(queue),
        "--checkout", str(REPO), "--action", "run", "--tick-seconds", "0.5",
        "--max-ticks", "4", "--exit-when-drained",
    )
    assert code == 0 and run["launches"] == 1, run
    # C2: in-flight work with a recorded step.
    resumable = _envelope(
        "cp-task", replay=ReplayClass.CHECKPOINT_RESUMABLE, steps=("PLAN", "APPLY", "VERIFY")
    )
    persist_envelope(root, resumable)
    persist_checkpoint(root, _checkpoint(resumable, sequence=1, last_step="PLAN"))
    # C3: an UNCERTAIN quarantine, and a pause.
    _quarantined_task(root, "unc-task")
    resident.request_pause(root, requested_by="operator:test")
    return root, queue


def _mutate_c2(root: Path) -> None:
    path = _checkpoint_file(root, "cp-task")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["last_completed_step"] = None
    raw["next_action"] = "start cp-task from its first step"
    raw.pop("self_digest")
    resealed = seal_checkpoint(ContinuationCheckpoint.model_validate(raw))
    write_json_atomic(path, resealed.model_dump(mode="json"))


def _mutate_c3_pause(root: Path) -> None:
    assert resident.clear_pause(root) is True


def _mutate_c3_quarantine(root: Path) -> None:
    envelope = _envelope("unc-task", replay=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT)
    persist_checkpoint(root, _checkpoint(envelope, sequence=2, terminal=True))


def _mutate_c4(root: Path) -> None:
    state = load_state(root)
    assert state is not None
    state.tasks["gate-done"].launches += 1
    state.total_launches += 1
    persist_state(root, state)


_T10_CASES: dict[str, tuple[str | None, Callable[[Path], None] | None]] = {
    "control": (None, None),
    "C1_revision_moved": ("service_and_candidate", None),
    "C2_checkpoint_rederived_from_step_zero": ("state_recovery", _mutate_c2),
    "C3_pause_cleared": ("pause_and_uncertain", _mutate_c3_pause),
    "C3_quarantine_cleared": ("pause_and_uncertain", _mutate_c3_quarantine),
    "C4_completed_task_relaunched": ("no_double_execution", _mutate_c4),
}


@needs_identity
@pytest.mark.parametrize("case", sorted(_T10_CASES))
def test_T10_discrimination_gate_each_mutation_flips_exactly_its_criterion(
    tmp_path: Path, case: str
) -> None:
    """Break each of C1..C4 in turn; each must flip exactly its own criterion.

    A mutation that flips nothing is VACUOUS and fails as such -- it is never
    reported as a pass.
    """
    root, queue = _t10_fixture(tmp_path)
    taken, taken_code = _in_process(
        "program", "dispatcher", "--state-root", str(root), "--queue-root", str(queue),
        "--action", "restart",
    )
    assert taken_code == 0, taken
    witness = resident.read_restart_witness(root)
    assert witness is not None
    # Guard the fixture: nothing below may pass for lack of anything to judge.
    assert witness.terminal_task_ids == ("gate-done",)
    assert set(witness.in_flight_checkpoints) == {"cp-task", "unc-task"}
    assert witness.reconcile_required_task_ids == ("unc-task",)
    assert witness.paused is True
    assert witness.revision_head and witness.revision_tree

    target, mutation = _T10_CASES[case]
    checkout = _other_git_checkout(tmp_path) if case == "C1_revision_moved" else REPO
    if mutation is not None:
        mutation(root)

    # The restart: a new dispatcher, in this (different) process.
    resident.ResidentDispatcher(
        root=root,
        queue_root=queue,
        checkout=checkout,
        tick_seconds=0.5,
        wake_quantum_seconds=0.1,
        sleeper=lambda _seconds: None,
    ).run(max_ticks=1)

    payload, code = _in_process(
        "program", "dispatcher", "--state-root", str(root), "--queue-root", str(queue),
        "--action", "restart-verify",
    )
    verdict = payload["restart_verdict"]
    flipped = {name for name in CRITERIA if verdict[name] != "PASS"}
    if target is None:
        assert verdict == ALL_PASS, payload["evidence"]
        assert code == 0
        return
    if not flipped:
        pytest.fail(f"VACUOUS: mutation {case} flipped no criterion: {payload['evidence']}")
    assert flipped == {target}, (case, verdict, payload["evidence"])
    assert verdict[target] == "FAIL", (case, verdict, payload["evidence"])
    assert code != 0


# ====================================================== write boundary


@needs_identity
def test_restart_and_restart_verify_write_only_under_the_dispatcher_directory(
    tmp_path: Path,
) -> None:
    root, queue = _t10_fixture(tmp_path)
    outside_before = _snapshot(root, skip_dispatcher=True)
    queue_before = _snapshot(queue)
    dispatcher_before = _snapshot(resident.dispatcher_dir(root))

    delegate, code = _cli(
        "program", "dispatcher", "--state-root", str(root), "--queue-root", str(queue),
        "--action", "restart",
    )
    assert code == 0
    # The default keeps today's contract and adds the witness and the check.
    assert delegate["performed"] is False
    assert delegate["reason"] == "NOT_AUTHORIZED_FROM_HERE"
    assert any("--action restart-verify" in line for line in delegate["operator_commands"])
    _cli(
        "program", "dispatcher", "--state-root", str(root), "--queue-root", str(queue),
        "--action", "restart-verify",
    )
    _cli(
        "program", "dispatcher", "--state-root", str(root),
        "--action", "restart", "--mode", "supervised",
    )

    assert _snapshot(root, skip_dispatcher=True) == outside_before
    assert _snapshot(queue) == queue_before
    dispatcher_after = _snapshot(resident.dispatcher_dir(root))
    changed = {
        name
        for name in set(dispatcher_before) | set(dispatcher_after)
        if dispatcher_before.get(name) != dispatcher_after.get(name)
    }
    assert changed == {resident._RESTART_WITNESS_NAME, resident._RESTART_VERDICT_NAME}


def test_restart_wait_seconds_is_bounded(tmp_path: Path) -> None:
    for value in ("0", "-1", "601"):
        payload, code = _cli(
            "program", "dispatcher", "--state-root", str(tmp_path / "state"),
            "--action", "restart", "--wait-seconds", value,
        )
        assert payload["code"] == "RESTART_WAIT_SECONDS_OUT_OF_BOUNDS", (value, payload)
        assert code == 2
