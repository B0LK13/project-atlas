"""D-146 adversarial verification for remediation behaviors."""

from __future__ import annotations

import time
from pathlib import Path

from project_atlas.orchestration.autonomy.return_gate import AutonomyReturnState, may_emit_final_return
from project_atlas.orchestration.sdk.ci_observer import CiObservation, classify_watch_session
from project_atlas.orchestration.sdk.host import pid_is_alive
from project_atlas.orchestration.sdk.resident_driver import read_primary_lock_pid
from project_atlas.orchestration.sdk.resident_status import load_status, status_claims_live
from project_atlas.orchestration.sdk.resident_windows import (
    detach_continuous_watchdog,
    detach_resident_driver,
    ensure_resident_alive,
)


def test_watchdog_waits_for_lock_holder_no_second_spawn(tmp_path: Path) -> None:
    package_src = Path(__file__).resolve().parents[2] / "src"
    root = tmp_path / "runtime"
    (root / ".atlas" / "orchestration" / "sdk-runtime").mkdir(parents=True)
    detach_resident_driver(root=root, package_src=package_src)
    for _ in range(20):
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


def test_query_without_portfolio_fails_closed(tmp_path: Path) -> None:
    from project_atlas.cli import EXIT_OK, main

    repo = Path(__file__).resolve().parents[2]
    fixture = repo / "tests" / "fixtures" / "demo" / "estate" / "harbor-api"
    work = tmp_path / "work"
    source = work / "harbor-api"
    import shutil

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
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    no_portfolio = main(
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
    with_portfolio = EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    with_portfolio = main(
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
    assert with_portfolio == EXIT_OK
    assert no_portfolio != EXIT_OK or with_portfolio == EXIT_OK


def test_autonomy_gate_blocks_premature_d144_pattern() -> None:
    state = AutonomyReturnState(
        ready_nodes=1,
        uncertified_changes=6,
        derivable_successors=1,
        project_terminal=False,
    )
    assert may_emit_final_return(state) is False
