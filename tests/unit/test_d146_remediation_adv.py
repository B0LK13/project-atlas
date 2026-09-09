"""D-146 adversarial verification for remediation behaviors."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.return_gate import (
    AutonomyReturnState,
    may_emit_final_return,
)
from project_atlas.orchestration.sdk import resident_windows
from project_atlas.orchestration.sdk.ci_observer import CiObservation, classify_watch_session
from project_atlas.orchestration.sdk.resident_driver import (
    LOCK_NAME,
    acquire_primary_lock,
    read_primary_lock_pid,
)
from project_atlas.orchestration.sdk.resident_status import load_status
from project_atlas.orchestration.sdk.resident_windows import (
    detach_resident_driver,
    ensure_resident_alive,
)


def _terminate_resident_tree(pid: int) -> None:
    """Best-effort test cleanup for a `detach_resident_driver()`-spawned tree.

    D146 (native-Windows evidence, found while validating this successor):
    `os.kill(pid, signal.SIGTERM)` against these DETACHED_PROCESS /
    CREATE_NEW_PROCESS_GROUP children reproducibly raised
    ``OSError: [WinError 87] The parameter is incorrect`` on this class of
    host and never actually terminated the process -- a real, silent
    cleanup failure previously masked by `contextlib.suppress(OSError,
    ProcessLookupError)`. ``taskkill /F /T /PID`` reliably terminates both
    the target and any live descendants (verified: it also caught a child
    of the resident that `os.kill` alone would have missed entirely).
    Best-effort only -- this is cleanup, not an assertion.
    """
    if pid <= 0:
        return
    with contextlib.suppress(OSError):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )


def test_watchdog_waits_for_lock_holder_no_second_spawn(tmp_path: Path) -> None:
    """D146 successor (current-main, native-Windows-reproduced): current main's
    `detach_resident_driver()` returns bare `Popen.pid` unconditionally, which
    on a Windows venv whose `Scripts\\python.exe` is a launcher stub (confirmed
    on-host via binary size/hash against the base interpreter, and via
    `Win32_Process` ancestry: the real interpreter's `ParentProcessId` equals
    the launcher's PID) is the *launcher's* PID, not the resident's. Reproduced
    natively, repeatedly, with distinct PID pairs every time -- never PID 0,
    always a wrong-but-live PID. The successor makes `detach_resident_driver()`
    itself confirm the lock holder before returning (see its docstring), so by
    the time this function returns, `holder == returned_pid` is already the
    function's own contract -- this test's own poll loop below is now a
    redundant (harmless) safety net, not what makes the assertion pass.
    """
    package_src = Path(__file__).resolve().parents[2] / "src"
    root = tmp_path / "runtime"
    (root / ".atlas" / "orchestration" / "sdk-runtime").mkdir(parents=True)
    spawned_pid = detach_resident_driver(root=root, package_src=package_src)
    try:
        # Poll budget: 80 * 0.25s = 20s -- matches the internal budget
        # `detach_resident_driver()` already exhausted before returning;
        # this loop exists only so a slow-to-persist `resident-status.json`
        # (Finding B: status persistence lags lock acquisition, not
        # synchronized with it) doesn't make the assertions below flaky.
        for _ in range(80):
            if read_primary_lock_pid(root) > 0:
                break
            time.sleep(0.25)
        holder = read_primary_lock_pid(root)
        assert holder > 0
        assert holder == spawned_pid
        result = ensure_resident_alive(root=root, package_src=package_src)
        assert result["action"] == "noop"
        status = load_status(root)
        assert status.DUPLICATE_DISPATCH_COUNT == 0
    finally:
        # `detach_resident_driver()` spawns a genuinely detached OS
        # process (by design -- that's what "resident" means in
        # production) with no test-visible handle to wait/join on, so
        # nothing else in this process tree ever stops it. Left
        # unterminated, it idles indefinitely: on Windows specifically,
        # its watchdog loop periodically shells out to `gh run view`
        # against whatever `origin` remote happens to resolve at
        # process-start time in a bare `pytest-<n>/...` tmp_path
        # (nothing about this repo), which fails and pops a visible
        # console window per attempt -- a real, user-facing leak, not
        # just a lingering background process. `0` is a legitimate,
        # expected value here now (D146 successor: an unconfirmed
        # identity is honestly 0, not a guessed PID) -- there is nothing
        # confirmed to target in that case, so `_terminate_resident_tree`
        # (best-effort, PID-scoped, never broader) is a no-op on 0.
        _terminate_resident_tree(spawned_pid)


def test_detach_resident_driver_returns_authoritative_lock_holder_pid(
    tmp_path: Path,
) -> None:
    """D146 successor, isolated from the no-second-spawn scenario above: the
    PID `detach_resident_driver()` returns must itself already be the
    confirmed primary-lock holder -- not merely a live PID that happens to
    coincide with it. Cross-checked against `read_primary_lock_pid()` (the
    lock file the resident writes) directly; `load_status().GOVERNOR_PID` is
    checked with its own short bounded wait rather than asserted immediately
    (Finding B: `run_resident_loop()` writes the primary lock before it
    persists status, so the two are not synchronized).

    Negative control: on unpatched current main, `detach_resident_driver()`
    returns `Popen.pid` unconditionally -- reproducibly wrong on this class
    of Windows host (verified natively, repeatedly: launcher PID != lock
    holder PID, never PID 0).
    """
    package_src = Path(__file__).resolve().parents[2] / "src"
    root = tmp_path / "runtime"
    (root / ".atlas" / "orchestration" / "sdk-runtime").mkdir(parents=True)
    resolved_pid = detach_resident_driver(root=root, package_src=package_src)
    try:
        assert resolved_pid > 0
        assert resolved_pid == read_primary_lock_pid(root), (
            "detach_resident_driver()'s return value must already be the "
            "confirmed lock holder"
        )
        status = None
        for _ in range(20):
            status = load_status(root)
            if resolved_pid == status.GOVERNOR_PID:
                break
            time.sleep(0.25)
        assert status is not None and resolved_pid == status.GOVERNOR_PID, (
            "the resident's own self-reported os.getpid() must eventually "
            "agree with the confirmed identity (bounded wait: status "
            "persistence is not promised to be synchronized with lock "
            "acquisition, so this must not be asserted immediately)"
        )
    finally:
        _terminate_resident_tree(resolved_pid)


def test_read_primary_lock_pid_refuses_malformed_or_stale_lock(tmp_path: Path) -> None:
    """D146 successor test-matrix item 7: a malformed or stale lock file must
    resolve to "no confirmed holder" (0), never a value `detach_resident_
    driver()` could mistake for a live identity."""
    root = tmp_path / "runtime"
    lock_dir = root / ".atlas" / "orchestration" / "sdk-runtime"
    lock_dir.mkdir(parents=True)
    lock_path = lock_dir / LOCK_NAME

    lock_path.write_text("{not valid json", encoding="utf-8")
    assert read_primary_lock_pid(root) == 0

    # A syntactically valid but stale record: PID 0 is never a live process.
    lock_path.write_text(json.dumps({"pid": 0, "at": 0.0}), encoding="utf-8")
    assert read_primary_lock_pid(root) == 0

    # A confirmed-alive PID (this test process itself) round-trips.
    assert acquire_primary_lock(root)
    assert read_primary_lock_pid(root) == os.getpid()


class _FakePopen:
    """Minimal Popen stand-in: only ``pid``/``poll`` are consumed by the launch path."""

    def __init__(self, pid: int, *, exited: bool = False) -> None:
        self.pid = pid
        self._exited = exited
        self.args: list[str] | None = None
        self.kwargs: dict[str, object] = {}

    def poll(self) -> int | None:
        return 0 if self._exited else None


def _capture_popen(
    monkeypatch: pytest.MonkeyPatch, fake_pid: int = 4242, *, exited: bool = False
) -> _FakePopen:
    fake = _FakePopen(fake_pid, exited=exited)

    def _popen(args: list[str], **kwargs: object) -> _FakePopen:
        fake.args = list(args)
        fake.kwargs = dict(kwargs)
        return fake

    monkeypatch.setattr(resident_windows.subprocess, "Popen", _popen)
    return fake


def test_detach_resident_driver_prefers_announced_lock_holder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test-matrix item 1/8: when the resident announces itself (lock file)
    the returned identity must be the announced holder, never the spawned
    launcher PID -- and the host-identity receipt must record the same."""
    root = tmp_path / "runtime"
    package_src = tmp_path / "repo" / "src"
    package_src.mkdir(parents=True)
    fake = _capture_popen(monkeypatch, fake_pid=4242)
    # Holder announced on the very first poll: no sleeping required.
    monkeypatch.setattr(resident_windows, "read_primary_lock_pid", lambda _root: 7777)
    resolved = detach_resident_driver(root=root, package_src=package_src)
    assert resolved == 7777
    assert resolved != int(fake.pid)
    receipt = json.loads(
        (root / ".atlas" / "orchestration" / "sdk-runtime" / "supervisor-host.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["supervisor_pid"] == 7777
    assert (root / ".atlas" / "orchestration" / "sdk-runtime" / "supervisor.pid").read_text(
        encoding="utf-8"
    ).strip() == "7777"


def test_detach_resident_driver_returns_zero_when_never_announced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test-matrix item 6: a resident that never announces within the bounded
    poll budget (genuine startup failure, or a launcher-host quirk) must
    return 0 -- an explicit, honest "not confirmed" -- never the launcher's
    `Popen.pid` presented as if it were the resident's identity. D146: the
    old fallback (spawned PID) is exactly the bug this successor closes;
    "no worse than before" is not the bar -- the launcher PID was never a
    safe representation of the resident to begin with."""
    root = tmp_path / "runtime"
    package_src = tmp_path / "repo" / "src"
    package_src.mkdir(parents=True)
    fake = _capture_popen(monkeypatch, fake_pid=4242)
    monkeypatch.setattr(resident_windows, "read_primary_lock_pid", lambda _root: 0)
    monkeypatch.setattr(resident_windows, "_RESIDENT_STARTUP_POLL_ATTEMPTS", 3)
    sleeps: list[float] = []
    monkeypatch.setattr(
        resident_windows.time, "sleep", lambda sec: sleeps.append(float(sec))
    )
    resolved = detach_resident_driver(root=root, package_src=package_src)
    assert resolved == 0
    assert resolved != int(fake.pid)
    assert len(sleeps) == 3
    assert all(sec == resident_windows._RESIDENT_STARTUP_POLL_INTERVAL_SEC for sec in sleeps)


def test_detach_resident_driver_stops_polling_once_launcher_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test-matrix item 5 (Finding A, correctly scoped -- not a blind
    `proc.poll() is not None: break`): once the launched process object has
    exited, continuing to sleep out the rest of the poll budget cannot
    produce a different outcome -- the fallback is 0 either way now, so
    stopping early is a pure latency win, never a risk of returning a wrong
    PID (that risk existed only under the old "fall back to the launcher
    PID" semantics this successor removes). One immediate final check
    happens before giving up, so a holder announced in the same instant the
    launcher exits is still observed."""
    root = tmp_path / "runtime"
    package_src = tmp_path / "repo" / "src"
    package_src.mkdir(parents=True)
    _capture_popen(monkeypatch, fake_pid=4242, exited=True)
    monkeypatch.setattr(resident_windows, "read_primary_lock_pid", lambda _root: 0)
    monkeypatch.setattr(resident_windows, "_RESIDENT_STARTUP_POLL_ATTEMPTS", 80)
    sleeps: list[float] = []
    monkeypatch.setattr(
        resident_windows.time, "sleep", lambda sec: sleeps.append(float(sec))
    )
    resolved = detach_resident_driver(root=root, package_src=package_src)
    assert resolved == 0
    # Stopped on the very first iteration -- never slept out the full
    # 80-attempt budget just because the (already-exited) process object
    # said so before this fix.
    assert sleeps == []


def test_detach_resident_driver_invokes_exact_interpreter_module_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D146-A/D146-C non-spawn defense: the launch command must be an exact
    ``<interpreter> -m project_atlas.cli orchestrator governor-resident-run``
    invocation with the package source pinned on PYTHONPATH -- never a bare
    ``atlas`` resolved from PATH, which on this class of host can silently
    execute an unrelated stale Atlas installation (see the D146-C finding)."""
    root = tmp_path / "runtime"
    package_src = tmp_path / "repo" / "src"
    package_src.mkdir(parents=True)
    fake = _capture_popen(monkeypatch, fake_pid=4242)
    monkeypatch.setattr(resident_windows, "read_primary_lock_pid", lambda _root: 4242)
    interpreter = tmp_path / "repo" / ".venv" / "Scripts" / "python.exe"
    detach_resident_driver(root=root, package_src=package_src, python=str(interpreter))
    assert fake.args is not None
    assert fake.args == [
        str(interpreter),
        "-m",
        "project_atlas.cli",
        "orchestrator",
        "governor-resident-run",
        "--root",
        str(root),
        "--detached-worker",
    ]
    env = fake.kwargs["env"]
    assert isinstance(env, dict)
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(package_src)
    assert fake.kwargs["stdin"] is subprocess.DEVNULL
    assert fake.kwargs["cwd"] == str(root)


def test_observer_timeout_pending_is_not_ci_fail() -> None:
    obs = CiObservation(head_sha="a" * 40, status="PENDING")
    disp = classify_watch_session(
        watch_exit_code=1, watch_timed_out=True, observation=obs
    )
    assert disp == "CI_STILL_RUNNING"
    assert disp != "CI_TERMINAL_FAIL"


def test_observer_exit_without_observation_is_observer_exited() -> None:
    disp = classify_watch_session(
        watch_exit_code=1, watch_timed_out=True, observation=None
    )
    assert disp == "OBSERVER_EXITED"


def test_ask2_after_build_portfolio_passes(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    fixture = repo / "tests" / "fixtures" / "demo" / "estate" / "harbor-api"
    work = tmp_path / "work"
    source = work / "harbor-api"
    shutil.copytree(fixture, source)
    manifest = work / "manifest.json"
    vault = work / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    assert (
        main(
            [
                "ask2",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
                "--question",
                "audit logging",
                "--json",
            ]
        )
        == EXIT_OK
    )


def test_autonomy_gate_blocks_premature_d144_pattern() -> None:
    state = AutonomyReturnState(
        ready_nodes=1,
        uncertified_changes=6,
        derivable_successors=1,
        project_terminal=False,
    )
    assert may_emit_final_return(state) is False
