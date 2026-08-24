"""D-164 fresh #428 successor — SDK supervisor stop/double-start ops."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import patch

import pytest

from project_atlas.orchestration.sdk.cli import run_governor_service, run_supervisor_stop
from project_atlas.orchestration.sdk.host import (
    SUPERVISOR_LOCK_NAME,
    acquire_supervisor_lock,
    assert_single_supervisor_or_raise,
    clear_supervisor_stop,
    host_state_dir,
    read_supervisor_lock_pid,
    release_supervisor_lock,
    request_supervisor_stop,
    stop_requested,
)
from project_atlas.orchestration.sdk.models import SdkRuntimeError
from project_atlas.orchestration.sdk.supervisor import DurableAtlasSupervisor


def test_request_supervisor_stop_writes_file(tmp_path) -> None:
    request_supervisor_stop(tmp_path)
    assert stop_requested(tmp_path)
    clear_supervisor_stop(tmp_path)
    assert not stop_requested(tmp_path)


def test_double_start_rejected_when_live_holder(tmp_path) -> None:
    acquire_supervisor_lock(tmp_path)
    with (
        patch("project_atlas.orchestration.sdk.host.pid_is_alive", return_value=True),
        patch("project_atlas.orchestration.sdk.host.os.getpid", return_value=99999),
        pytest.raises(SdkRuntimeError, match="another live supervisor") as exc_info,
    ):
        assert_single_supervisor_or_raise(tmp_path)
    assert exc_info.value.code == "SERVICE_DOUBLE_START"
    release_supervisor_lock(tmp_path)


def test_run_supervisor_stop_json(tmp_path) -> None:
    payload, code = run_supervisor_stop(root=tmp_path)
    assert code == 0
    assert payload["stop_requested"] is True
    assert stop_requested(tmp_path)


def test_governor_service_double_start_returns_error(tmp_path) -> None:
    acquire_supervisor_lock(tmp_path)
    with (
        patch("project_atlas.orchestration.sdk.host.pid_is_alive", return_value=True),
        patch("project_atlas.orchestration.sdk.host.os.getpid", return_value=88888),
        patch(
            "project_atlas.orchestration.sdk.windows_bridge.apply_windows_discovery_patch",
            return_value=None,
        ),
    ):
        payload, code = run_governor_service(root=tmp_path, use_fake=True, max_cycles=0)
    release_supervisor_lock(tmp_path)
    assert code == 1
    assert payload["code"] == "SERVICE_DOUBLE_START"


def test_run_forever_honors_stop_file(tmp_path) -> None:
    acquire_supervisor_lock(tmp_path)
    clear_supervisor_stop(tmp_path)
    supervisor = DurableAtlasSupervisor.create(
        tmp_path, use_fake=True, poll_interval_sec=0.01
    )
    request_supervisor_stop(tmp_path)
    status = asyncio.run(supervisor.run_forever())
    release_supervisor_lock(tmp_path)
    assert status.running is False
    assert read_supervisor_lock_pid(tmp_path) == 0


def test_concurrent_acquire_only_one_holder(tmp_path) -> None:
    """PR476-IV-P1-001 — exclusive create prevents TOCTOU double acquisition."""
    results: list[bool] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        results.append(acquire_supervisor_lock(tmp_path))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [False, True]
    release_supervisor_lock(tmp_path)


def test_corrupt_lock_fails_closed(tmp_path) -> None:
    lock_path = host_state_dir(tmp_path) / SUPERVISOR_LOCK_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("{not-json", encoding="utf-8")
    assert acquire_supervisor_lock(tmp_path) is False


def test_stale_lock_reclaimed_when_holder_dead(tmp_path) -> None:
    lock_path = host_state_dir(tmp_path) / SUPERVISOR_LOCK_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text('{"pid": 424242}\n', encoding="utf-8")
    with patch("project_atlas.orchestration.sdk.host.pid_is_alive", return_value=False):
        assert acquire_supervisor_lock(tmp_path) is True
    release_supervisor_lock(tmp_path)
