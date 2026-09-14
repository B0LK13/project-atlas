"""F-02: a reused PID must refuse BEFORE the restart launch boundary."""

import sys
from pathlib import Path
from unittest.mock import patch

from test_program_restart_operator_recovery import (
    _declare,
    _in_process,
    _Owned,
    _snapshot,
    _write_heartbeat,
    needs_identity,
)

from project_atlas.orchestration.program import resident
from project_atlas.orchestration.program.adapters.base import process_start_identity


@needs_identity
def test_reused_pid_refuses_before_any_launch_or_control_write(tmp_path: Path) -> None:
    owned = _Owned()
    try:
        stranger = owned.sleeper()
        root = tmp_path / "state"
        _write_heartbeat(root, pid=stranger.pid, identity="linux:0-reused-stranger")
        _declare(root, [sys.executable, "-c", "raise SystemExit(0)"])
        before = _snapshot(root)
        with patch("subprocess.Popen", side_effect=AssertionError("F02 reached Popen")):
            payload, code = _in_process(
                "program",
                "dispatcher",
                "--state-root",
                str(root),
                "--action",
                "restart",
                "--mode",
                "supervised",
                "--wait-seconds",
                "0.1",
            )
        assert code != 0
        assert payload["code"] == "RESTART_IDENTITY_UNVERIFIABLE"
        assert payload["started"] is False
        assert payload["stopped"] is False
        assert _snapshot(root) == before
        assert stranger.poll() is None
        assert process_start_identity(stranger.pid) == owned.identity_of(stranger.pid)
    finally:
        owned.cleanup()


@needs_identity
def test_identity_change_after_witness_refuses_before_drain(tmp_path: Path) -> None:
    owned = _Owned()
    try:
        stranger = owned.sleeper()
        root = tmp_path / "state"
        _write_heartbeat(root, pid=stranger.pid, identity=owned.identity_of(stranger.pid))
        _declare(root, [sys.executable, "-c", "raise SystemExit(0)"])
        original = resident.write_restart_witness

        def change_after_write(root, witness):
            path = original(root, witness)
            _write_heartbeat(root, pid=stranger.pid, identity="linux:reused-after-pre")
            return path

        with (
            patch(
                "project_atlas.orchestration.program.continuation_cli.write_restart_witness",
                side_effect=change_after_write,
            ),
            patch("subprocess.Popen", side_effect=AssertionError("late reuse reached Popen")),
            patch(
                "project_atlas.orchestration.program.continuation_cli.request_drain",
                side_effect=AssertionError("late reuse reached drain"),
            ),
        ):
            payload, code = _in_process(
                "program",
                "dispatcher",
                "--state-root",
                str(root),
                "--action",
                "restart",
                "--mode",
                "supervised",
            )
        assert code != 0 and payload["code"] == "RESTART_IDENTITY_UNVERIFIABLE"
        assert stranger.poll() is None
    finally:
        owned.cleanup()
