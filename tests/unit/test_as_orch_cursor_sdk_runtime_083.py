"""D-083 Cursor SDK supervisor: fake follow-up, idempotency, recovery, CI observer."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.continuation_broker import (
    BACKEND,
    PRIMARY_CONTINUATION_BACKEND,
    BrokerPhase,
    SuccessorKind,
    enqueue_successor,
    recover_broker,
    supersede_legacy_hook_successor,
)
from project_atlas.orchestration.autonomy.models import CANONICAL_REPOSITORY_IDENTITY
from project_atlas.orchestration.sdk.backend import FakeCursorSDKBackend
from project_atlas.orchestration.sdk.ci_observer import CiObservation, persist_observation
from project_atlas.orchestration.sdk.cost_guard import CostGuard
from project_atlas.orchestration.sdk.idempotency import build_idempotency_key
from project_atlas.orchestration.sdk.models import AgentRole, RunStatus, ScheduleRequest
from project_atlas.orchestration.sdk.recovery import recover_runtime
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.scheduler import DagToAgentScheduler, ReadyWorkItem
from project_atlas.orchestration.sdk.supervisor import DurableAtlasSupervisor

PIN = "7e797468a2eca37c959920912b1fa264df4be638"
TREE = "3cb40645c343edf8f8ab95f6ddf3a819e2110ef2"


def _stack(tmp_path: Path) -> tuple[FakeCursorSDKBackend, DagToAgentScheduler]:
    agents = CloudAgentRegistry(tmp_path)
    runs = RunRegistry(tmp_path)
    pool = AgentRolePool(agents)
    backend = FakeCursorSDKBackend(agents_reg=agents, runs_reg=runs, pool=pool)
    sched = DagToAgentScheduler(
        backend=backend, agents=agents, runs=runs, pool=pool, cost=CostGuard(runs)
    )
    return backend, sched


def test_followup_run_without_human(tmp_path: Path) -> None:
    backend, sched = _stack(tmp_path)
    first = ReadyWorkItem(
        role=AgentRole.LOCAL_AUTHENTIC_WORKER,
        package_id="AS-ORCH-CONTINUATION-BROKER-001",
        node_id="SDK-SMOKE-A",
        cycle_id="CYCLE-SDK-A",
        dag_generation=83,
        base_main=PIN,
        prompt="bounded read-only smoke A",
    )
    started = asyncio.run(sched.assign_and_start([first]))
    assert len(started.started) == 1
    run_a = started.started[0]
    assert run_a.status == RunStatus.FINISHED
    follow = ReadyWorkItem(
        role=AgentRole.LOCAL_AUTHENTIC_WORKER,
        package_id="AS-ORCH-CONTINUATION-BROKER-001",
        node_id="SDK-SMOKE-B",
        cycle_id="CYCLE-SDK-B",
        dag_generation=83,
        base_main=PIN,
        prompt="bounded follow-up B",
        prefer_followup=True,
        existing_agent_id=run_a.agent_id,
        attempt=2,
    )
    second = asyncio.run(sched.assign_and_start([follow]))
    assert len(second.started) == 1
    run_b = second.started[0]
    assert run_b.agent_id == run_a.agent_id
    assert run_b.run_id != run_a.run_id
    assert backend.context_len(run_a.agent_id) == 2


def test_idempotent_retry_does_not_duplicate(tmp_path: Path) -> None:
    backend, _sched = _stack(tmp_path)
    req = ScheduleRequest(
        role=AgentRole.IMPLEMENTER,
        package_id="AS-ORCH-CONTINUATION-BROKER-001",
        node_id="NODE-1",
        cycle_id="CYCLE-1",
        dag_generation=1,
        attempt=1,
        base_main=PIN,
        prompt="do work",
    )
    first = asyncio.run(backend.create_and_send(req))
    again = asyncio.run(backend.create_and_send(req))
    assert first.run_id == again.run_id
    key = build_idempotency_key(
        dag_generation=1, node_id="NODE-1", role=AgentRole.IMPLEMENTER, attempt=1
    )
    assert first.idempotency_key == key


def test_supervisor_restart_recovers_without_duplicate(tmp_path: Path) -> None:
    backend, _sched = _stack(tmp_path)
    backend.auto_finish = False
    req = ScheduleRequest(
        role=AgentRole.REMEDIATOR,
        package_id="AS-ORCH-CONTINUATION-BROKER-001",
        node_id="NODE-R",
        cycle_id="CYCLE-R",
        dag_generation=2,
        attempt=1,
        base_main=PIN,
        prompt="remediate",
    )
    run = asyncio.run(backend.create_and_send(req))
    assert run.status == RunStatus.RUNNING
    report = asyncio.run(
        recover_runtime(backend=backend, agents=backend.agents_reg, runs=backend.runs_reg)
    )
    assert run.agent_id in report.resumed_agents
    recovered = backend.runs_reg.get(run.run_id)
    assert recovered is not None
    assert recovered.run_id == run.run_id


def test_legacy_d081_successor_is_superseded_not_replayed(tmp_path: Path) -> None:
    enqueue_successor(
        tmp_path,
        cycle_id="D081-CI-0",
        kind=SuccessorKind.CI_PENDING_WITH_OBSERVER,
        trusted_main=PIN,
        trusted_tree=TREE,
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        next_action_class="MONITOR_EXACT_HEAD_CI",
    )
    updated = supersede_legacy_hook_successor(tmp_path, cycle_id="D081-CI-0")
    assert updated.phase == BrokerPhase.AWAITING_RESULT
    assert updated.external_wait_identity == "SUPERSEDED_BY_SDK_SUPERVISOR"
    assert recover_broker(tmp_path) is not None
    assert BACKEND == "CURSOR_STOP_HOOK_FOLLOWUP"
    assert PRIMARY_CONTINUATION_BACKEND == "CURSOR_SDK_DURABLE_AGENT_RUNTIME"


def test_ci_observer_persists_without_prompt(tmp_path: Path) -> None:
    obs = CiObservation(head_sha=PIN, run_id="32397435014", status="PENDING")
    path = persist_observation(tmp_path, obs)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["observer"] == "SDK_SUPERVISOR"
    assert payload["status"] == "PENDING"
    assert "prompt" not in payload


def test_independence_roles_cannot_reuse_implementer(tmp_path: Path) -> None:
    agents = CloudAgentRegistry(tmp_path)
    pool = AgentRolePool(agents)
    with pytest.raises(Exception, match="independence") as exc:
        pool.require_new_agent(
            AgentRole.INDEPENDENT_VERIFIER, reason="followup_from_implementer"
        )
    assert exc.value.code == "INDEPENDENCE_REQUIRED"


def test_cli_sdk_auth_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["orchestrator", "sdk-auth-status", "--root", str(tmp_path)]) == EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["cursor_api_key_available"] in {"YES", "NO"}
    assert out["merge_authorized"] is False


def test_supervisor_create_observe_only_without_key(tmp_path: Path) -> None:
    supervisor = DurableAtlasSupervisor.create(tmp_path, use_fake=True, max_cycles=1)
    assert supervisor.status.merge_authorized is False
    assert supervisor.status.next_machine_action_executing_or_scheduled is True
