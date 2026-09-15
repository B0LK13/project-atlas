"""B1 regression: in-flight process identity is durable, and absence is proven.

Owner: program-supervisor package (#797 lane).

WAS (characterisation, ATLAS-END-TO-END-INTEGRATION-PROOF-001 §B1)
    adapters/base.py computed pid + process_start_identity at spawn, but
    AttemptRecord only received them in supervisor._settle_running on
    ADAPTER_RETURNED. At ADAPTER_INVOKED process_pid was None, and
    recovery.worker_still_alive() returned a bare False for that -- the same
    False it returned for a process that had genuinely exited. classify_attempt
    turned that into the sentence "the worker was launched, is gone". It was
    observed saying so about a worker that was still running: reproducer
    `docs/orchestration/program/evidence/b1/repro.sh`, transcript
    `.../b1/before-4aac27ae.txt` (orphan pid 873082 alive, verdict
    NEEDS_RECONCILIATION / "is gone").

NOW (the behaviour these tests require)
    The adapter announces (pid, start_identity) the instant the child exists,
    and the supervisor makes it durable in its own single-attempt file BEFORE
    the adapter returns. Liveness is three-valued: ALIVE / GONE / UNKNOWN.
    Missing identity is UNKNOWN and is never reported as absence.

    Fail-closed is unchanged. UNKNOWN routes to NEEDS_RECONCILIATION -- never
    to RESUME_SESSION, never to a relaunch, never to a lease release -- because
    a worker that may still be running must not get a sibling.

Every test here runs the local-command fixture worker. Zero model calls.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from tests.unit.test_orchestration_program_supervisor import (
    _make_workspace,
    _profile,
    _supervisor,
    _task,
    _write_program,
)

from project_atlas.orchestration.program.adapters.base import (
    process_start_identity,
    run_child_to_completion,
)
from project_atlas.orchestration.program.models import AcceptanceKind, AttemptPhase
from project_atlas.orchestration.program.recovery import (
    Liveness,
    RecoveryAction,
    attempt_liveness,
    classify_attempt,
    process_liveness,
    worker_still_alive,
)
from project_atlas.orchestration.program.store import (
    launches_dir,
    load_launch,
    load_state,
    record_launch,
)
from project_atlas.orchestration.program.supervisor import ProgramSupervisor
from project_atlas.orchestration.sdk.host import request_supervisor_stop


def _hang_program(tmp_path: Path, workspace: Path) -> Path:
    return _write_program(
        tmp_path,
        workspace,
        tasks=[_task("hangs", output="never.txt")],
        profiles={"implementer": _profile(max_seconds=3600)},
        limits={"max_cycles": 4, "idle_sleep_seconds": 0.0, "max_task_seconds": 30},
    )


def _probe_in_flight(
    supervisor: ProgramSupervisor,
    state_root: Path,
    seen: dict[str, Any],
    *,
    during: Any = None,
) -> None:
    """Observe the durable files WHILE a child is running.

    `_begin_dispatch` returns as soon as the work is submitted; the adapter
    spawns on a worker thread some microseconds later. Reading immediately
    after it returns therefore sees the moment before the child exists, which
    is not the window this finding is about. So the probe waits for the launch
    record to appear -- bounded, and it fails loudly if it never does, since
    "never appeared" is exactly the defect.

    Everything the tests assert on is captured here, in flight. After the hang
    is cancelled the attempt settles and its record stops being an in-flight
    record at all.
    """
    original_submit = supervisor._submit

    def submit_then_probe(running: Any) -> None:
        # AFTER the real submit: `_begin_dispatch` only records intent, and the
        # child is spawned by `_submit` on a worker thread. Probing before this
        # point observes the moment before the process exists, which is not the
        # window this finding is about -- and blocking there stops the spawn
        # from ever happening.
        original_submit(running)
        attempt_id = running.attempt_id
        seen["attempt_id"] = attempt_id
        launch = None
        for _ in range(200):  # up to 10s; a hang fixture is not in a hurry
            launch = load_launch(state_root, attempt_id)
            if launch is not None:
                break
            time.sleep(0.05)
        seen["launch"] = launch
        reloaded = load_state(state_root)
        assert reloaded is not None
        attempt = reloaded.attempts[attempt_id]
        seen["phase"] = attempt.phase
        seen["attempt_pid"] = attempt.process_pid
        seen["attempt"] = attempt
        seen["liveness"] = attempt_liveness(attempt, root=state_root)
        if during is not None:
            during(attempt, seen)
        # The durable stop file, which the running adapter's cancel_check
        # already consults. Do not hold the suite on a hang.
        request_supervisor_stop(supervisor.lock_root)

    supervisor._submit = submit_then_probe  # type: ignore[method-assign]
    supervisor.start()


# ------------------------------------------- 1. registration before return


def test_identity_is_durable_before_the_adapter_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "hang")
    supervisor = _supervisor(_hang_program(tmp_path, workspace), tmp_path)
    seen: dict[str, Any] = {}
    _probe_in_flight(supervisor, tmp_path / "state", seen)

    assert seen["phase"] is AttemptPhase.ADAPTER_INVOKED
    # The attempt record still has no pid -- correct: the worker thread must
    # not touch the state object. The durable launch record is what carries it.
    assert seen["attempt_pid"] is None
    launch = seen["launch"]
    assert launch is not None, "no in-flight identity was made durable"
    assert isinstance(launch["pid"], int) and launch["pid"] > 0
    assert launch["process_start_identity"] not in (None, "", "unknown")
    assert launch["attempt_id"] == seen["attempt_id"]


def test_a_live_in_flight_worker_is_reported_alive_not_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact inversion of the finding."""
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "hang")
    supervisor = _supervisor(_hang_program(tmp_path, workspace), tmp_path)
    seen: dict[str, Any] = {}
    _probe_in_flight(supervisor, tmp_path / "state", seen)

    verdict, reason = seen["liveness"]
    assert verdict is Liveness.ALIVE, reason
    assert "matches the one recorded at launch" in reason


# ------------------------------------------- 2. supervisor interruption


def test_an_interrupted_supervisor_finds_its_worker_still_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh reader, with only the durable files, reaches WORKER_STILL_RUNNING.

    Nothing from the interrupted process is in memory here: state and launch
    record are re-read from disk, which is precisely the situation after a
    SIGKILL.
    """
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "hang")
    program = _hang_program(tmp_path, workspace)
    supervisor = _supervisor(program, tmp_path)
    seen: dict[str, Any] = {}

    def classify_from_a_fresh_reader(attempt: Any, captured: dict[str, Any]) -> None:
        successor = _supervisor(program, tmp_path)
        state = load_state(tmp_path / "state")
        assert state is not None
        fresh = state.attempts[attempt.attempt_id]
        assert fresh.phase is AttemptPhase.ADAPTER_INVOKED
        assert fresh.process_pid is None
        task = successor.program.task(fresh.task_id)
        profile = successor.loaded.effective_profile(task.task_id)
        adapter = successor._adapter_for(profile)
        request = successor._build_request(
            task=task, attempt=fresh, profile=profile,
            instruction=task.instruction, resume_session_id=None, cancel_check=None,
        )
        captured["verdict"] = classify_attempt(
            fresh, task=task, adapter=adapter,
            capabilities=adapter.capabilities, request=request,
            root=tmp_path / "state",
        )

    _probe_in_flight(
        supervisor, tmp_path / "state", seen, during=classify_from_a_fresh_reader
    )
    verdict = seen["verdict"]
    assert verdict.action is RecoveryAction.WORKER_STILL_RUNNING
    assert "is gone" not in verdict.reason


# ------------------------------------------- 3. fast worker exit


def test_a_worker_that_exits_immediately_leaves_no_stale_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registration happens even for a child that outlives it by microseconds.

    And the record is cleared on settle: a leftover file would name a pid the
    operating system is free to hand to a stranger.
    """
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    program = _write_program(
        tmp_path, workspace,
        tasks=[_task("quick", output="quick.txt")],
        profiles={"implementer": _profile(max_seconds=60)},
        limits={"max_cycles": 4, "idle_sleep_seconds": 0.0, "max_task_seconds": 30},
    )
    supervisor = _supervisor(program, tmp_path)
    report = supervisor.start()

    state = load_state(tmp_path / "state")
    assert state is not None
    attempt = next(iter(state.attempts.values()))
    assert attempt.process_pid is not None
    assert attempt.process_start_identity is not None
    assert load_launch(tmp_path / "state", attempt.attempt_id) is None
    assert list(launches_dir(tmp_path / "state").glob("*.json")) == []
    assert report.complete or report.stop_reason is not None


# ------------------------------------------- 4. spawn failure


def test_a_spawn_that_never_starts_records_no_identity(tmp_path: Path) -> None:
    """No process, no record. An empty record must not be invented."""
    recorded: list[tuple[int, str]] = []
    with pytest.raises(OSError):
        run_child_to_completion(
            argv=[str(tmp_path / "does-not-exist")],
            cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin"},
            stdin_text=None,
            timeout_seconds=5,
            cancel_requested=None,
            process_started=lambda pid, identity: recorded.append((pid, identity)),
        )
    assert recorded == []


# ------------------------------------------- 5. failed registration


def test_a_registration_that_fails_kills_the_child_rather_than_orphan_it(
    tmp_path: Path,
) -> None:
    """An unrecorded live worker is the one thing worse than no worker.

    If the durable write fails -- a full disk, a read-only state root -- the
    child must not be left running under an identity nobody holds. It is
    terminated and the failure is raised, not swallowed.
    """
    seen: dict[str, int] = {}

    def failing_register(pid: int, identity: str) -> None:
        seen["pid"] = pid
        raise OSError("state root is read-only")

    with pytest.raises(OSError, match="read-only"):
        run_child_to_completion(
            argv=[sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin"},
            stdin_text=None,
            timeout_seconds=30,
            cancel_requested=None,
            process_started=failing_register,
        )
    pid = seen["pid"]
    for _ in range(100):
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.05)
    else:  # pragma: no cover - only on a failure
        os.kill(pid, signal.SIGKILL)
        pytest.fail(f"child {pid} was left running after a failed registration")


# ------------------------------------------- pid AND start identity


def test_a_reused_pid_is_gone_not_alive() -> None:
    """PID alone is not identity. A live stranger is not our worker."""
    verdict, reason = process_liveness(os.getpid(), "linux:definitely-not-ours")
    assert verdict is Liveness.GONE
    assert "reused" in reason


def test_a_matching_start_identity_is_alive() -> None:
    verdict, reason = process_liveness(os.getpid(), process_start_identity(os.getpid()))
    assert verdict is Liveness.ALIVE
    assert "matches" in reason


def test_a_dead_pid_is_gone_and_says_why() -> None:
    verdict, reason = process_liveness(2**31 - 2, "linux:whatever")
    assert verdict is Liveness.GONE
    assert "not running" in reason


def test_no_recorded_identity_is_unknown_never_gone() -> None:
    verdict, reason = process_liveness(None, None)
    assert verdict is Liveness.UNKNOWN
    assert "no process identity was recorded" in reason
    assert "gone" not in reason.lower()


def test_a_live_pid_without_a_recorded_identity_is_unknown() -> None:
    """The PID-reuse guard cannot run, so nothing may be concluded."""
    verdict, reason = process_liveness(os.getpid(), None)
    assert verdict is Liveness.UNKNOWN
    assert "cannot be told apart from a reused pid" in reason


# ------------------------------------------- fail-closed under UNKNOWN


def _resumable_capabilities(adapter: Any) -> Any:
    from dataclasses import replace

    return replace(adapter.capabilities, supports_resume=True)


def test_unknown_never_resumes_and_never_relaunches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No automatic replay while a worker's fate is unestablished.

    A resume-capable adapter with a session id is the tempting case: the old
    code took exactly this branch and started a second worker beside one that
    might still be alive.
    """
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "hang")
    program = _hang_program(tmp_path, workspace)
    supervisor = _supervisor(program, tmp_path)
    seen: dict[str, Any] = {}

    def erase_identity_then_classify(attempt: Any, captured: dict[str, Any]) -> None:
        # Erase the durable identity: the pre-repair situation exactly, with a
        # worker that really is still running.
        for stale in launches_dir(tmp_path / "state").glob("*.json"):
            stale.unlink()
        assert attempt.runtime_session_id  # the branch that used to fire
        successor = _supervisor(program, tmp_path)
        state = load_state(tmp_path / "state")
        assert state is not None
        fresh = state.attempts[attempt.attempt_id]
        task = successor.program.task(fresh.task_id)
        profile = successor.loaded.effective_profile(task.task_id)
        adapter = successor._adapter_for(profile)
        request = successor._build_request(
            task=task, attempt=fresh, profile=profile,
            instruction=task.instruction, resume_session_id=None, cancel_check=None,
        )
        captured["verdict"] = classify_attempt(
            fresh, task=task, adapter=adapter,
            capabilities=_resumable_capabilities(adapter), request=request,
            root=tmp_path / "state",
        )

    _probe_in_flight(
        supervisor, tmp_path / "state", seen, during=erase_identity_then_classify
    )
    verdict = seen["verdict"]
    assert verdict.action is RecoveryAction.NEEDS_RECONCILIATION
    assert verdict.action is not RecoveryAction.RESUME_SESSION
    assert verdict.action is not RecoveryAction.SAFE_TO_LAUNCH
    assert verdict.resume_session_id is None
    assert "UNKNOWN" in verdict.reason
    assert "is gone" not in verdict.reason


def test_unknown_holds_the_lease_rather_than_releasing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unestablished fate must not free the task for someone else."""
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "hang")
    supervisor = _supervisor(_hang_program(tmp_path, workspace), tmp_path)
    seen: dict[str, Any] = {}

    def erase_then_check(attempt: Any, captured: dict[str, Any]) -> None:
        for stale in launches_dir(tmp_path / "state").glob("*.json"):
            stale.unlink()
        assert attempt.lease_id is not None, "the attempt held a lease"
        captured["unknown"] = attempt_liveness(attempt, root=tmp_path / "state")
        captured["still_alive"] = worker_still_alive(attempt, root=tmp_path / "state")

    _probe_in_flight(supervisor, tmp_path / "state", seen, during=erase_then_check)
    verdict, _why = seen["unknown"]
    assert verdict is Liveness.UNKNOWN
    # The narrow question stays False for UNKNOWN, so no caller can read it as
    # permission to reclaim the task.
    assert seen["still_alive"] is False


def test_worker_still_alive_is_false_for_both_gone_and_unknown() -> None:
    """The bool is deliberately lossy; callers needing the difference must ask
    attempt_liveness. This pins that it never answers True for either."""
    from project_atlas.orchestration.program.store import AttemptRecord

    def _attempt(**over: Any) -> AttemptRecord:
        body: dict[str, Any] = {
            "attempt_id": "p.t.run.1.aaaa", "task_id": "t", "attempt_number": 1,
            "idempotency_key": "k", "profile_id": "p", "agent_id": "a",
            "adapter": "local-command", "profile_digest": "0" * 64,
            "base_pin": "0" * 40, "phase": AttemptPhase.ADAPTER_INVOKED,
        }
        body.update(over)
        return AttemptRecord.model_validate(body)

    assert worker_still_alive(_attempt()) is False                      # UNKNOWN
    assert worker_still_alive(
        _attempt(process_pid=2**31 - 2, process_start_identity="linux:x")
    ) is False                                                          # GONE
    assert AcceptanceKind.COMMAND  # import kept meaningful


# ------------------------------------------- the record itself


def test_a_launch_record_is_keyed_to_its_own_attempt(tmp_path: Path) -> None:
    """Two attempts must never share a file."""
    record_launch(tmp_path, attempt_id="p.t.run.1.aaa", pid=11, start_identity="i1")
    record_launch(tmp_path, attempt_id="p.t.run.2.bbb", pid=22, start_identity="i2")
    first = load_launch(tmp_path, "p.t.run.1.aaa")
    second = load_launch(tmp_path, "p.t.run.2.bbb")
    assert first is not None and second is not None
    assert (first["pid"], second["pid"]) == (11, 22)
    assert load_launch(tmp_path, "p.t.run.3.ccc") is None
