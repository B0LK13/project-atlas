"""D-146 adversarial verification for remediation behaviors."""

from __future__ import annotations

import shutil
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
    detach_resident_driver(root=root, package_src=package_src)
    # Poll budget: 80 * 0.25s = 20s. The resident driver's startup cost is
    # subprocess spawn + a full project_atlas package import, which on a
    # slow-I/O checkout (e.g. WSL2 9p/DrvFs mounts) has been measured at
    # ~6.5s -- past the previous 5s (20 * 0.25s) budget, causing this test
    # to fail closed even though the driver was healthy and just slow to
    # start. 20s gives real headroom on slow hosts while the loop still
    # breaks early (no added wall-clock cost) on fast ones.
    for _ in range(80):
        if read_primary_lock_pid(root) > 0:
            break
        time.sleep(0.25)
    holder = read_primary_lock_pid(root)
    assert holder > 0
    result = ensure_resident_alive(root=root, package_src=package_src)
    assert result["action"] == "noop"
    status = load_status(root)
    assert status.DUPLICATE_DISPATCH_COUNT == 0


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
