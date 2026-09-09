"""AS-MISSION-VERTICAL-SLICE-001 -- load-bearing regression coverage for
the real production KNOWLEDGE -> DEVELOPMENT -> RECOVERY path in
`project_atlas.orchestration.mission`.

Every crash scenario below kills a REAL, separate OS process at a
controlled checkpoint state (via `_mission_run_worker.py`), not a
simulated/mocked failure -- the same discipline established across this
session's `resident_driver`/`os_lock` work. Every spawn is bounded by an
explicit timeout and produces no visible console window on Windows.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from project_atlas.orchestration.mission.adapter import ShellCommandAdapter
from project_atlas.orchestration.mission.context_packet import (
    check_context_staleness,
    compile_mission_context,
)
from project_atlas.orchestration.mission.execution import (
    WorkspaceUnavailableError,
    load_checkpoint,
    start_mission_run,
)
from project_atlas.orchestration.mission.lease import (
    acquire_mission_lease,
    read_mission_lease_state,
)
from project_atlas.orchestration.mission.recovery import reconcile_mission_run

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_WORKER = str(Path(__file__).with_name("_mission_run_worker.py"))
_TIMEOUT = 20.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _kill_tree(proc: subprocess.Popen) -> None:
    """`proc.kill()` alone is NOT sufficient here: this worktree's venv
    `python.exe` is a launcher/trampoline stub (confirmed by binary size,
    the same D146 pattern seen elsewhere this session) that can spawn the
    REAL interpreter as a child process -- killing only the launcher PID
    leaves that real child (the one actually holding the mission lease)
    alive. Tree-kill on Windows (`taskkill /F /T /PID`); process-group
    kill on POSIX."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            creationflags=_NO_WINDOW,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(Exception):
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# KNOWLEDGE
# ---------------------------------------------------------------------------


def test_context_packet_compiles_from_real_repository_documents():
    """Real ADRs, real backlog, real worklog tail -- not fixtures."""
    packet = compile_mission_context(
        _repo_root(),
        mission_id="M-TEST-001",
        objective="test the mission vertical slice itself",
        keywords=["lock", "governor", "resident"],
        trusted_policy={"MERGE_AUTHORIZATION": "NO"},
    )
    assert packet.base_head  # real git HEAD, not a placeholder
    assert len(packet.base_head) == 40
    assert len(packet.decisions) > 0, "must find at least one real matching ADR"
    assert all(d.source.blob_hash for d in packet.decisions)
    # Retrieved material is data: nothing in trusted_policy came from retrieval.
    assert packet.trusted_policy == {"MERGE_AUTHORIZATION": "NO"}


def test_context_packet_manifest_shows_inclusion_and_exclusion():
    packet = compile_mission_context(
        _repo_root(),
        mission_id="M-TEST-002",
        objective="test manifest honesty",
        keywords=["atlas", "vault", "governance"],  # broad, likely > max_sources hits
        max_sources=2,
    )
    assert len(packet.decisions) <= 2
    assert isinstance(packet.manifest.excluded_sources, list)
    assert isinstance(packet.manifest.approx_tokens, int)
    assert packet.manifest.approx_tokens >= 0


def test_context_staleness_detects_a_real_source_change(tmp_path):
    """Deliberately mutate a real tracked file, confirm the packet flags
    it as superseded, then restore it byte-for-byte."""
    repo_root = _repo_root()
    target = repo_root / "docs" / "adr" / "ADR-001-wp001-foundation-decisions.md"
    original = target.read_text(encoding="utf-8")
    packet = compile_mission_context(
        repo_root, mission_id="M-TEST-003", objective="staleness", keywords=["foundation"]
    )
    assert any(
        d.source.path.endswith("ADR-001-wp001-foundation-decisions.md") for d in packet.decisions
    )
    try:
        target.write_text(original + "\nTEST MUTATION -- reverted immediately\n", encoding="utf-8")
        report = check_context_staleness(repo_root, packet)
        assert any(p.endswith("ADR-001-wp001-foundation-decisions.md") for p in report.superseded)
    finally:
        target.write_text(original, encoding="utf-8")
        report_after = check_context_staleness(repo_root, packet)
        assert not any(
            p.endswith("ADR-001-wp001-foundation-decisions.md") for p in report_after.superseded
        )


# ---------------------------------------------------------------------------
# DEVELOPMENT (lease + adapter + execution)
# ---------------------------------------------------------------------------


def test_lease_cross_process_exclusion(tmp_path):
    """A real separate process holding the lease excludes this process."""
    workspace = tmp_path / "ws"
    go_file = tmp_path / "go"
    holder = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "STARTED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        go_file.write_text("go", encoding="utf-8")
        deadline = time.time() + _TIMEOUT
        while not (workspace / "mission-lease-receipt.json").is_file() and time.time() < deadline:
            time.sleep(0.05)
        assert (workspace / "mission-lease-receipt.json").is_file(), "holder never published"

        assert acquire_mission_lease(workspace, run_id="intruder") is False
        state = read_mission_lease_state(workspace)
        assert state.held is True
    finally:
        _kill_tree(holder)


def test_shell_command_adapter_real_execution(tmp_path):
    adapter = ShellCommandAdapter(command=(sys.executable, "-c", "print('hello from adapter')"))
    result = adapter.run(workspace=tmp_path, timeout_sec=10.0)
    assert result.ok is True
    assert result.returncode == 0
    assert "hello from adapter" in result.stdout


def test_shell_command_adapter_timeout_is_bounded(tmp_path):
    adapter = ShellCommandAdapter(
        command=(sys.executable, "-c", "import time; time.sleep(30)")
    )
    start = time.perf_counter()
    result = adapter.run(workspace=tmp_path, timeout_sec=1.0)
    elapsed = time.perf_counter() - start
    assert result.ok is False
    assert elapsed < 10.0, "timeout must actually bound the call, not merely be advisory"


def test_full_mission_run_end_to_end(tmp_path):
    repo_root = _repo_root()
    packet = compile_mission_context(
        repo_root, mission_id="M-E2E-001", objective="end to end", keywords=["lock"]
    )
    workspace = tmp_path / "ws"
    adapter = ShellCommandAdapter(command=(sys.executable, "-c", "print('real work happened')"))
    result = start_mission_run(
        mission_id="M-E2E-001",
        context=packet,
        adapter=adapter,
        workspace=workspace,
        adapter_timeout_sec=10.0,
    )
    assert result.checkpoint.state == "COMPLETE"
    assert result.adapter_result is not None
    assert result.adapter_result.ok is True
    reloaded = load_checkpoint(workspace)
    assert reloaded is not None
    assert reloaded.state == "COMPLETE"
    # Lease is released after a normal completion -- a fresh run can claim it.
    assert read_mission_lease_state(workspace).held is False


def test_workspace_unavailable_raises_not_silently_proceeds(tmp_path):
    """Must use a REAL separate process as the holder: `acquire_mission_lease`
    is deliberately idempotent for the SAME process re-claiming a workspace
    it already owns (mirrors `acquire_primary_lock`'s own contract), so a
    same-process "intruder" would not exercise the exclusion path this test
    is actually checking."""
    workspace = tmp_path / "ws"
    go_file = tmp_path / "go"
    holder = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "STARTED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        go_file.write_text("go", encoding="utf-8")
        deadline = time.time() + _TIMEOUT
        while not (workspace / "mission-lease-receipt.json").is_file() and time.time() < deadline:
            time.sleep(0.05)
        assert (workspace / "mission-lease-receipt.json").is_file(), "holder never published"

        repo_root = _repo_root()
        packet = compile_mission_context(
            repo_root, mission_id="M-BUSY-001", objective="busy", keywords=["lock"]
        )
        adapter = ShellCommandAdapter(command=(sys.executable, "-c", "print('should not run')"))
        with pytest.raises(WorkspaceUnavailableError):
            start_mission_run(
                mission_id="M-BUSY-001",
                context=packet,
                adapter=adapter,
                workspace=workspace,
                adapter_timeout_sec=5.0,
            )
        # The intruder's rejected attempt must not have disturbed the real
        # holder's checkpoint-less, lease-only ownership.
        assert read_mission_lease_state(workspace).held is True
    finally:
        _kill_tree(holder)


# ---------------------------------------------------------------------------
# RECOVERY
# ---------------------------------------------------------------------------


def test_reconcile_no_run_found(tmp_path):
    result = reconcile_mission_run(tmp_path / "never-touched")
    assert result.outcome == "NO_RUN_FOUND"
    assert result.safe_to_retry is True


def test_reconcile_still_running_is_ui_reconnect_not_recovery(tmp_path):
    """A live worker (real separate process) means this is a UI-reconnect
    situation -- reconciliation must not disturb it."""
    workspace = tmp_path / "ws"
    go_file = tmp_path / "go"
    holder = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "ADAPTER_INVOKED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        go_file.write_text("go", encoding="utf-8")
        deadline = time.time() + _TIMEOUT
        while not (workspace / "mission-run-checkpoint.json").is_file() and time.time() < deadline:
            time.sleep(0.05)
        result = reconcile_mission_run(workspace)
        assert result.outcome == "STILL_RUNNING"
        assert result.safe_to_retry is False
        # Reconciliation must not have disturbed the live holder's lease.
        assert read_mission_lease_state(workspace).held is True
    finally:
        _kill_tree(holder)


def test_reconcile_worker_crash_before_adapter_invoked_is_safe_to_retry(tmp_path):
    workspace = tmp_path / "ws"
    go_file = tmp_path / "go"
    proc = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "STARTED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    go_file.write_text("go", encoding="utf-8")
    deadline = time.time() + _TIMEOUT
    while not (workspace / "mission-run-checkpoint.json").is_file() and time.time() < deadline:
        time.sleep(0.05)
    _kill_tree(proc)  # real crash -- no graceful shutdown

    result = reconcile_mission_run(workspace)
    assert result.outcome == "SAFE_TO_RETRY_NEVER_STARTED_EXTERNAL_EFFECT"
    assert result.safe_to_retry is True


def test_reconcile_worker_crash_mid_adapter_invocation_is_uncertain(tmp_path):
    """The core ambiguous-outcome case: the adapter was invoked but the
    worker died before any confirmed/failed outcome was recorded. Must
    NEVER be reported as safe to retry -- the whole point of RECOVERY."""
    workspace = tmp_path / "ws"
    go_file = tmp_path / "go"
    proc = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "ADAPTER_INVOKED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    go_file.write_text("go", encoding="utf-8")
    deadline = time.time() + _TIMEOUT
    checkpoint_file = workspace / "mission-run-checkpoint.json"
    while time.time() < deadline:
        if checkpoint_file.is_file():
            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                if data.get("state") == "ADAPTER_INVOKED":
                    break
            except json.JSONDecodeError:
                pass
        time.sleep(0.02)
    _kill_tree(proc)

    result = reconcile_mission_run(workspace)
    assert result.outcome == "UNCERTAIN_REQUIRES_RECONCILIATION"
    assert result.safe_to_retry is False


def test_reconcile_worker_crash_after_confirmed_outcome_is_known(tmp_path):
    """The adapter's outcome WAS recorded before the crash -- known, not
    ambiguous, even though COMPLETE/lease-release never happened."""
    workspace = tmp_path / "ws"
    go_file = tmp_path / "go"
    proc = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "ADAPTER_CONFIRMED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    go_file.write_text("go", encoding="utf-8")
    deadline = time.time() + _TIMEOUT
    checkpoint_file = workspace / "mission-run-checkpoint.json"
    while time.time() < deadline:
        if checkpoint_file.is_file():
            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                if data.get("state") == "ADAPTER_CONFIRMED":
                    break
            except json.JSONDecodeError:
                pass
        time.sleep(0.02)
    _kill_tree(proc)

    result = reconcile_mission_run(workspace)
    assert result.outcome == "KNOWN_OUTCOME_CLEANUP_ONLY"
    assert result.safe_to_retry is False
    assert result.checkpoint is not None
    assert result.checkpoint.result is not None
    assert result.checkpoint.result["ok"] is True


def test_reconcile_already_complete(tmp_path):
    repo_root = _repo_root()
    packet = compile_mission_context(
        repo_root, mission_id="M-DONE-001", objective="done", keywords=["lock"]
    )
    workspace = tmp_path / "ws"
    adapter = ShellCommandAdapter(command=(sys.executable, "-c", "print('done')"))
    start_mission_run(
        mission_id="M-DONE-001",
        context=packet,
        adapter=adapter,
        workspace=workspace,
        adapter_timeout_sec=10.0,
    )
    result = reconcile_mission_run(workspace)
    assert result.outcome == "ALREADY_COMPLETE"
    assert result.safe_to_retry is False


def test_no_process_leaks(tmp_path):
    """Every worker this module spawns must be killable and reach a real
    exit within a bounded wait -- this test only asserts the harness's
    own bookkeeping is self-consistent, matching the same-named test in
    the primary-lock suite."""
    go_file = tmp_path / "go"
    workspace = tmp_path / "ws"
    proc = subprocess.Popen(
        [sys.executable, _WORKER, str(workspace), "ADAPTER_CONFIRMED", str(go_file)],
        creationflags=_NO_WINDOW,
        start_new_session=(sys.platform != "win32"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        go_file.write_text("go", encoding="utf-8")
        deadline = time.time() + _TIMEOUT
        checkpoint_file = workspace / "mission-run-checkpoint.json"
        while time.time() < deadline:
            if checkpoint_file.is_file():
                try:
                    data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                    if data.get("state") == "ADAPTER_CONFIRMED":
                        break
                except json.JSONDecodeError:
                    pass
            time.sleep(0.02)
    finally:
        _kill_tree(proc)
        assert proc.poll() is not None
