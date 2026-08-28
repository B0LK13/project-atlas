"""AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001 / D-128 tests.

PENDING_EXTERNAL_EVENT != GLOBAL_SCHEDULER_BLOCK.
Cases A-H + idempotency + stall + owner-held isolation.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.orchestration.sdk.external_observers import (
    ObserverStatus,
    consume_terminal_event,
    load_consumed_event_ids,
    load_liveness,
    load_observer_registry,
    make_observer,
    park_observer_backoff,
    pending_external_count,
    register_observer,
)
from project_atlas.orchestration.sdk.models import AgentRole
from project_atlas.orchestration.sdk.nonblocking_scheduler import (
    apply_ci_poll_result,
    bounded_sleep_seconds,
    classify_idle,
    detect_stall,
    prove_two_ci_do_not_block_dispatch,
    register_ci_observer,
    scheduler_tick,
    select_ready_for_dispatch,
)
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem


def _ready(
    node_id: str,
    *,
    package_id: str = "PKG-X",
    score: int = 0,
) -> ReadyWorkItem:
    return ReadyWorkItem(
        role=AgentRole.READ_ONLY_ANALYST,
        package_id=package_id,
        node_id=node_id,
        cycle_id="c1",
        dag_generation=1,
        base_main="a" * 40,
        prompt="analyze",
        critical_path_score=score,
    )


def test_case_a_one_ci_running_one_ready_dispatches(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-1",
        package_id="PKG-CI",
        generation=1,
        run_id="111",
        expected_head="b" * 40,
        now=1000.0,
    )
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("ready-1", package_id="PKG-OTHER", score=10)],
        capacity=2,
        now=1000.0,
        ci_poll_snapshots={"ci-1": ("in_progress", None)},
    )
    assert len(tick.dispatched) == 1
    assert tick.dispatched[0].node_id == "ready-1"
    assert tick.global_blocking_ci_waits == 0
    assert pending_external_count(load_observer_registry(tmp_path)) >= 1


def test_case_b_two_ci_five_ready_fills_capacity(tmp_path: Path) -> None:
    for i in (1, 2):
        register_ci_observer(
            tmp_path,
            observer_id=f"ci-{i}",
            package_id=f"PKG-CI-{i}",
            generation=1,
            run_id=str(100 + i),
            expected_head="c" * 40,
            now=1000.0,
        )
    ready = [_ready(f"n{i}", package_id=f"P{i}", score=10 - i) for i in range(5)]
    tick = scheduler_tick(tmp_path, ready=ready, capacity=3, now=1000.0)
    assert len(tick.dispatched) == 3
    assert tick.pending_external >= 2
    assert tick.global_blocking_ci_waits == 0


def test_case_c_ci_running_resource_yield_continues(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-y",
        package_id="PKG-CI",
        generation=1,
        run_id="222",
        expected_head="d" * 40,
        now=1000.0,
    )
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("ok"), _ready("busy")],
        capacity=2,
        parked_node_ids={"busy"},
        now=1000.0,
    )
    assert [d.node_id for d in tick.dispatched] == ["ok"]
    assert tick.resource_yield_owner_required is False
    assert classify_idle(
        ready_count=0, pending_external=1, owner_held=0, runnable_independent=1
    ) in {"ACTIVE", "BOUNDED_IDLE"}


def test_case_d_ci_fail_unrelated_continues(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-fail",
        package_id="PKG-FAIL",
        generation=1,
        run_id="333",
        expected_head="e" * 40,
        now=1000.0,
    )
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("other", package_id="PKG-OK")],
        capacity=1,
        now=1000.0,
        ci_poll_snapshots={"ci-fail": ("completed", "failure")},
    )
    assert len(tick.dispatched) == 1
    obs = load_observer_registry(tmp_path).observers["ci-fail"]
    assert obs.status == ObserverStatus.TERMINAL_FAIL
    assert "ci-fail" in tick.terminal_consumed


def test_case_e_rate_limit_parks_observer_scheduler_continues(tmp_path: Path) -> None:
    register_observer(
        tmp_path,
        make_observer(
            observer_id="ci-rl",
            observer_type="GITHUB_CI",
            package_id="PKG-CI",
            generation=1,
            external_id="444",
            now=1000.0,
            status=ObserverStatus.RUNNING,
        ),
    )
    parked = park_observer_backoff(tmp_path, "ci-rl", now=1000.0, error="RATE_LIMIT")
    assert parked.status == ObserverStatus.PARKED
    assert parked.next_poll_at > 1000.0
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("keep-going")],
        capacity=1,
        now=1000.0,
    )
    assert len(tick.dispatched) == 1
    assert tick.resource_yield_owner_required is False


def test_case_f_cloud_and_ci_pending_local_verification_dispatches(tmp_path: Path) -> None:
    register_observer(
        tmp_path,
        make_observer(
            observer_id="cloud-1",
            observer_type="CURSOR_CLOUD_RUN",
            package_id="PKG-CLOUD",
            generation=1,
            external_id="bc-1",
            now=1000.0,
            status=ObserverStatus.RUNNING,
        ),
    )
    register_ci_observer(
        tmp_path,
        observer_id="ci-f",
        package_id="PKG-CI",
        generation=1,
        run_id="555",
        expected_head="f" * 40,
        now=1000.0,
    )
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("local-iv", package_id="PKG-IV", score=50)],
        capacity=1,
        now=1000.0,
    )
    assert tick.dispatched[0].node_id == "local-iv"
    assert tick.pending_external >= 2


def test_case_g_only_externals_bounded_idle_not_owner(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-g",
        package_id="PKG-CI",
        generation=1,
        run_id="666",
        expected_head="g" * 40,
        now=1000.0,
    )
    tick = scheduler_tick(tmp_path, ready=[], capacity=1, now=1000.0)
    assert tick.governor_state == "BOUNDED_IDLE"
    assert tick.dispatched == []


def test_case_h_owner_held_only_is_owner_required(tmp_path: Path) -> None:
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("held", package_id="PKG-HELD")],
        capacity=1,
        owner_held_packages={"PKG-HELD"},
        owner_held_count=1,
        now=1000.0,
    )
    assert tick.dispatched == []
    assert tick.governor_state == "OWNER_REQUIRED"


def test_owner_held_does_not_block_other_ready(tmp_path: Path) -> None:
    tick = scheduler_tick(
        tmp_path,
        ready=[
            _ready("held", package_id="PKG-A"),
            _ready("go", package_id="PKG-B", score=5),
        ],
        capacity=2,
        owner_held_packages={"PKG-A"},
        owner_held_count=1,
        now=1000.0,
    )
    assert [d.node_id for d in tick.dispatched] == ["go"]


def test_event_consumption_idempotent(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-idemp",
        package_id="PKG",
        generation=1,
        run_id="777",
        expected_head="h" * 40,
        now=1000.0,
    )
    apply_ci_poll_result(
        tmp_path, "ci-idemp", raw_status="completed", conclusion="success", now=1000.0
    )
    key = "ci-idemp:TERMINAL_PASS:777"
    assert consume_terminal_event(tmp_path, observer_id="ci-idemp", event_key=key) is True
    assert consume_terminal_event(tmp_path, observer_id="ci-idemp", event_key=key) is False
    assert key in load_consumed_event_ids(tmp_path)
    tick = scheduler_tick(tmp_path, ready=[], now=1001.0)
    assert tick.duplicate_event_skips >= 1


def test_stall_detection_and_self_reconcile(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-stall",
        package_id="PKG-CI",
        generation=1,
        run_id="888",
        expected_head="i" * 40,
        now=1000.0,
    )
    # Seed liveness with stale progress.
    from project_atlas.orchestration.sdk.external_observers import (
        SchedulerLiveness,
        persist_liveness,
    )

    persist_liveness(
        tmp_path,
        SchedulerLiveness(LAST_PROGRESS_AT=900.0, LAST_SCHEDULER_TICK=900.0),
    )
    assert detect_stall(
        load_liveness(tmp_path),
        now=1000.0,
        ready_count=1,
        pending_external=1,
        stall_interval_sec=30.0,
    )
    tick = scheduler_tick(
        tmp_path,
        ready=[_ready("unstick")],
        capacity=1,
        now=1000.0,
        stall_interval_sec=30.0,
    )
    assert tick.stall_detected is True
    assert tick.stall_reconciled is True
    assert len(tick.dispatched) == 1


def test_bounded_sleep_caps_long_wake() -> None:
    assert bounded_sleep_seconds(next_wake_at=10_000.0, now=0.0, cap_sec=5.0) == 5.0
    assert bounded_sleep_seconds(next_wake_at=2.0, now=0.0, cap_sec=5.0) == 2.0


def test_priority_ordering() -> None:
    items = [
        _ready("low", score=1),
        _ready("high", score=99),
        _ready("mid", score=10),
    ]
    selected = select_ready_for_dispatch(items, capacity=2)
    assert [s.node_id for s in selected] == ["high", "mid"]


def test_two_running_ci_do_not_block_dispatch(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-431",
        package_id="AS-CODER-ALPHA-DEMO-READINESS-001",
        generation=1,
        run_id="32498760059",
        expected_head="48a80aaf40e4d1c79564d7fbeb0f6af85aa0ea25",
        now=1000.0,
    )
    register_ci_observer(
        tmp_path,
        observer_id="ci-432",
        package_id="AS-ORCH-DURABLE-LEASE-PROJECTION-001",
        generation=1,
        run_id="32498766361",
        expected_head="1b5491d3a984ccc5c0181b243b8373333e1115b6",
        now=1000.0,
    )
    tick = prove_two_ci_do_not_block_dispatch(
        tmp_path,
        ready=[_ready("d128-proof", package_id="AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001")],
        now=1000.0,
    )
    assert len(tick.dispatched) == 1
    assert tick.pending_external == 2


def test_restart_reconstructs_observers(tmp_path: Path) -> None:
    register_ci_observer(
        tmp_path,
        observer_id="ci-restart",
        package_id="PKG",
        generation=1,
        run_id="999",
        expected_head="j" * 40,
        now=1000.0,
    )
    # Simulate process restart: reload from disk.
    reg = load_observer_registry(tmp_path)
    assert "ci-restart" in reg.observers
    assert reg.observers["ci-restart"].external_id == "999"
    tick = scheduler_tick(tmp_path, ready=[_ready("after-restart")], now=1000.0)
    assert len(tick.dispatched) == 1


def test_scheduler_ingest_does_not_wait_nonterminal(tmp_path: Path) -> None:
    """B-class guard: nonterminal runs are polled, not waited upon."""
    import asyncio
    from datetime import UTC, datetime

    from project_atlas.orchestration.sdk.backend import FakeCursorSDKBackend
    from project_atlas.orchestration.sdk.cost_guard import CostGuard
    from project_atlas.orchestration.sdk.models import (
        PACKAGE_ID,
        AgentRecord,
        AgentRole,
        AgentRuntime,
        AgentState,
        RunRecord,
        RunStatus,
    )
    from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
    from project_atlas.orchestration.sdk.role_pool import AgentRolePool
    from project_atlas.orchestration.sdk.scheduler import DagToAgentScheduler

    def _utc_now() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    async def _run() -> None:
        agents = CloudAgentRegistry(tmp_path)
        runs = RunRegistry(tmp_path)
        pool = AgentRolePool(agents)
        backend = FakeCursorSDKBackend(agents_reg=agents, runs_reg=runs, pool=pool)
        agents.upsert(
            AgentRecord(
                agent_id="agent-test0001",
                role=AgentRole.IMPLEMENTER,
                runtime=AgentRuntime.LOCAL,
                state=AgentState.BUSY,
                package_id=PACKAGE_ID,
                base_main="a" * 40,
                created_at=_utc_now(),
            )
        )
        runs.upsert(
            RunRecord(
                run_id="run-nonterm-1",
                agent_id="agent-test0001",
                role=AgentRole.IMPLEMENTER,
                package_id=PACKAGE_ID,
                node_id="n1",
                cycle_id="c1",
                dag_generation=1,
                attempt=1,
                status=RunStatus.RUNNING,
                prompt_digest="b" * 64,
                idempotency_key="idemp-nonterm-1",
                started_at=_utc_now(),
            )
        )
        sched = DagToAgentScheduler(
            backend=backend,
            agents=agents,
            runs=runs,
            pool=pool,
            cost=CostGuard(runs),
            root=tmp_path,
        )
        ingested = await sched.ingest_completions()
        assert ingested == []
        still = runs.get("run-nonterm-1")
        assert still is not None and still.status == RunStatus.RUNNING

    asyncio.run(_run())
