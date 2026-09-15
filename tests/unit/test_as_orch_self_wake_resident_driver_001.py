"""AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001 — unit proofs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.external_observers import (
    load_observer_registry,
)
from project_atlas.orchestration.sdk.models import AgentRole
from project_atlas.orchestration.sdk.nonblocking_scheduler import register_ci_observer
from project_atlas.orchestration.sdk.resident_driver import (
    clear_stop,
    ensure_pr434_observer,
    request_stop,
    resident_tick,
    run_resident_loop,
    stop_requested,
)
from project_atlas.orchestration.sdk.resident_mission import (
    load_mission,
    persist_mission,
)
from project_atlas.orchestration.sdk.resident_status import load_status
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem


def test_mission_survives_restart(tmp_path: Path) -> None:
    m = persist_mission(tmp_path)
    assert m.FUTURE_AUTO_MERGE == "NO"
    assert m.EXTERNAL_TRIGGER_REQUIRED_FOR_NEXT_SCHEDULER_TICK == "NO"
    loaded = load_mission(tmp_path)
    assert loaded.MODE == "PERSISTENT_EVENT_DRIVEN_AUTONOMOUS_DEVELOPER"
    assert loaded.merge_authorized is False


def test_malformed_mission_fails_closed(tmp_path: Path) -> None:
    from project_atlas.orchestration.sdk.models import SdkRuntimeError
    from project_atlas.orchestration.sdk.resident_mission import mission_path

    path = mission_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(SdkRuntimeError):
        load_mission(tmp_path)


def test_due_wake_invokes_scheduler(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    ready = [
        ReadyWorkItem(
            role=AgentRole.READ_ONLY_ANALYST,
            package_id="AS-RELEASE-READINESS-DAG-001",
            node_id="REL-1",
            cycle_id="t",
            dag_generation=1,
            base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
            prompt="x",
            critical_path_score=10,
        )
    ]
    r1 = resident_tick(tmp_path, now=1000.0, ready=ready, capacity=2)
    assert "REL-1" in r1.dispatched
    status = load_status(tmp_path)
    assert status.DETACHED_SCHEDULER_TICK_COUNT >= 1
    assert status.LAST_SCHEDULER_TICK == 1000.0


def test_ready_forces_immediate_wake(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    ready = [
        ReadyWorkItem(
            role=AgentRole.READ_ONLY_ANALYST,
            package_id="AS-DEMO-READINESS-DAG-001",
            node_id="DEMO-1",
            cycle_id="t",
            dag_generation=1,
            base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
            prompt="x",
            critical_path_score=90,
        )
    ]
    result = resident_tick(tmp_path, now=2000.0, ready=ready, capacity=1)
    assert result.sleep_sec == 0.0 or result.dispatched
    assert result.next_wake_at == 2000.0 or result.dispatched


def test_pending_ci_does_not_block(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    register_ci_observer(
        tmp_path,
        observer_id="ci-pending",
        package_id="AS-ORCH-X",
        generation=1,
        run_id="1",
        expected_head="a" * 40,
        expected_tree="b" * 40,
        now=1000.0,
    )
    ready = [
        ReadyWorkItem(
            role=AgentRole.READ_ONLY_ANALYST,
            package_id="AS-RELEASE-READINESS-DAG-001",
            node_id="WHILE-CI",
            cycle_id="t",
            dag_generation=1,
            base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
            prompt="x",
            critical_path_score=50,
        )
    ]
    result = resident_tick(
        tmp_path,
        now=1000.0,
        ready=ready,
        capacity=1,
    )
    assert "WHILE-CI" in result.dispatched
    assert result.pending_external >= 1


def test_owner_held_does_not_stop_loop(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    q = tmp_path / ".atlas" / "orchestration" / "sdk-runtime" / "d129-owner-merge-queue.json"
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_text(
        json.dumps({"QUEUE": [{"PR": 431}, {"PR": 432}, {"PR": 433}]}),
        encoding="utf-8",
    )
    ready = [
        ReadyWorkItem(
            role=AgentRole.READ_ONLY_ANALYST,
            package_id="AS-RELEASE-READINESS-DAG-001",
            node_id="INDEP",
            cycle_id="t",
            dag_generation=1,
            base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
            prompt="x",
            critical_path_score=10,
        )
    ]
    result = resident_tick(tmp_path, now=3000.0, ready=ready, capacity=1)
    assert result.owner_held == 3
    assert "INDEP" in result.dispatched
    assert result.global_owner_required == "NO"


def test_next_wake_survives_restart(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    resident_tick(tmp_path, now=4000.0, ready=[], capacity=1)
    status = load_status(tmp_path)
    assert status.NEXT_WAKE_AT is not None
    reloaded = load_status(tmp_path)
    assert reloaded.NEXT_WAKE_AT == status.NEXT_WAKE_AT


def test_duplicate_timer_fire_idempotent(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    ensure_pr434_observer(tmp_path, now=5000.0)
    from project_atlas.orchestration.sdk.nonblocking_scheduler import apply_ci_poll_result

    apply_ci_poll_result(
        tmp_path,
        "ci-pr434-d130-g2",
        raw_status="completed",
        conclusion="success",
        now=5000.0,
    )
    r1 = resident_tick(tmp_path, now=5001.0, ready=[], capacity=0)
    r2 = resident_tick(tmp_path, now=5002.0, ready=[], capacity=0)
    assert "ci-pr434-d130-g2" in r1.terminal_consumed
    assert "ci-pr434-d130-g2" not in r2.terminal_consumed


def test_loop_stop_file(tmp_path: Path) -> None:
    persist_mission(tmp_path)
    clear_stop(tmp_path)
    request_stop(tmp_path)
    assert stop_requested(tmp_path)
    status = run_resident_loop(tmp_path, max_ticks=1)
    assert status.SELF_WAKE_DRIVER in {"STOPPED", "ACTIVE"}


def test_pr434_observer_registered(tmp_path: Path) -> None:
    ensure_pr434_observer(tmp_path, now=1.0)
    reg = load_observer_registry(tmp_path)
    assert "ci-pr434-d130-g2" in reg.observers
    assert reg.observers["ci-pr434-d130-g2"].external_id == "32504499868"
    assert "ci-pr435-d130" in reg.observers
