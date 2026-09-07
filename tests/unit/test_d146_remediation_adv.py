"""D-146 adversarial verification for remediation behaviors."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import time
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.return_gate import (
    AutonomyReturnState,
    may_emit_final_return,
)
from project_atlas.orchestration.sdk.ci_observer import CiObservation, classify_watch_session
from project_atlas.orchestration.sdk.resident_driver import read_primary_lock_pid
from project_atlas.orchestration.sdk.resident_status import load_status
from project_atlas.orchestration.sdk.resident_windows import (
    detach_resident_driver,
    ensure_resident_alive,
)


def test_watchdog_waits_for_lock_holder_no_second_spawn(tmp_path: Path) -> None:
    package_src = Path(__file__).resolve().parents[2] / "src"
    root = tmp_path / "runtime"
    (root / ".atlas" / "orchestration" / "sdk-runtime").mkdir(parents=True)
    # D146 (native-Windows evidence, current-main successor): the original
    # rationale here -- "captured directly from the spawn call, not derived
    # from polling" -- stopped being true and stopped being safe. On a
    # Windows venv whose `Scripts\python.exe` is CPython's launcher stub
    # (confirmed by binary size/checksum against the base interpreter its
    # own `pyvenv.cfg` names, and by `Win32_Process` ancestry: the launcher
    # re-execs the real interpreter as its *child*), `Popen.pid` -- what
    # "the spawn call" used to return unconditionally -- names the launcher,
    # not the process that runs the resident loop and actually calls
    # `acquire_primary_lock`. Reproduced against unpatched
    # `detach_resident_driver()`: `holder != spawned_pid` every time on this
    # class of host, never PID 0 -- a wrong-but-live PID, not a missing one,
    # so the reviewer finding above (a *timeout* leaving no PID to clean up)
    # and this one (a *wrong* PID that happens to resolve, via the
    # launcher's own child-lifetime handling on this host) are independent
    # failure modes. `detach_resident_driver()` now polls internally with
    # the identical bounded budget below and returns the confirmed
    # lock-holder PID when it observes one within budget, falling back to
    # the spawned PID -- preserving the original "always something to clean
    # up" property -- only if that poll times out, which the loop below,
    # unchanged, will also then correctly observe.
    spawned_pid = detach_resident_driver(root=root, package_src=package_src)
    try:
        # Poll budget: 80 * 0.25s = 20s. The resident driver's startup
        # cost is subprocess spawn + a full project_atlas package
        # import, which on a slow-I/O checkout (e.g. WSL2 9p/DrvFs
        # mounts) has been measured at ~6.5s -- past the previous 5s
        # (20 * 0.25s) budget, causing this test to fail closed even
        # though the driver was healthy and just slow to start. 20s
        # gives real headroom on slow hosts while the loop still breaks
        # early (no added wall-clock cost) on fast ones.
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
        # just a lingering background process. Best-effort, PID-scoped
        # (never broader): always targets the exact PID this test spawned
        # -- unconditionally, regardless of which assertion above failed
        # or whether the poll loop ever observed it -- and swallows every
        # failure mode (already exited, permission denied, PID reused by
        # an unrelated process on a platform without PID-generation
        # protection) since this is cleanup, not an assertion.
        with contextlib.suppress(OSError, ProcessLookupError):
            os.kill(spawned_pid, signal.SIGTERM)


def test_detach_resident_driver_returns_authoritative_lock_holder_pid(
    tmp_path: Path,
) -> None:
    """D146-A, isolated from the no-second-spawn scenario above: the PID
    `detach_resident_driver()` returns must itself already be the confirmed
    primary-lock holder -- not merely a live PID that happens to coincide
    with it. Cross-checked two independent ways: against
    `read_primary_lock_pid()` (the lock file the resident writes) and
    against `load_status().GOVERNOR_PID` (the resident's own `os.getpid()`
    self-report, set inside `run_resident_loop`) -- both must agree with the
    returned identity for it to be authoritative, not merely plausible.

    Negative control: this assertion fails on unpatched
    `detach_resident_driver()`, which returns `Popen.pid` unconditionally,
    reproducibly wrong on a Windows venv using CPython's launcher stub
    (verified natively: launcher PID != lock-holder PID, never PID 0).
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
        status = load_status(root)
        assert resolved_pid == status.GOVERNOR_PID, (
            "returned PID must match the resident's own self-reported "
            "os.getpid()"
        )
    finally:
        with contextlib.suppress(OSError, ProcessLookupError):
            os.kill(resolved_pid, signal.SIGTERM)


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
