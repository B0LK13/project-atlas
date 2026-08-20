"""Durable Atlas supervisor — persistent host process for SDK continuation.

Does not exit for CHECKPOINT_CONTINUE, RESOURCE_YIELD, CI/IV/ADV pending,
worker terminal, or owner-gate on one branch while independent work exists.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from project_atlas.orchestration.sdk.auth import (
    AuthDiscovery,
    BudgetConfig,
    discover_auth,
    record_auth_prerequisite,
)
from project_atlas.orchestration.sdk.backend import (
    CursorSDKExecutionBackend,
    ExecutionBackend,
    FakeCursorSDKBackend,
)
from project_atlas.orchestration.sdk.cli_execution_port import CursorAgentCliExecutionPort
from project_atlas.orchestration.sdk.cost_guard import CostGuard
from project_atlas.orchestration.sdk.models import (
    DIRECTIVE_ID,
    PACKAGE_ID,
    PRIMARY_BACKEND,
    STOP_HOOK_BACKEND,
)
from project_atlas.orchestration.sdk.recovery import RecoveryReport, recover_runtime
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.scheduler import (
    DagToAgentScheduler,
    ReadyWorkItem,
    ScheduleCycleResult,
)
from project_atlas.orchestration.sdk.security_gates import WorkerBackend

ReadyProvider = Callable[[], Awaitable[list[ReadyWorkItem]] | list[ReadyWorkItem]]


@dataclass
class SupervisorStatus:
    directive_id: str = DIRECTIVE_ID
    package_id: str = PACKAGE_ID
    primary_backend: str = PRIMARY_BACKEND
    stop_hook_backend: str = STOP_HOOK_BACKEND
    authentic_worker_backend: str = "NONE"
    cycles: int = 0
    running: bool = False
    auth: AuthDiscovery | None = None
    last_recovery: RecoveryReport | None = None
    last_cycle: ScheduleCycleResult | None = None
    human_scheduler_events: int = 0
    owner_action_required_now: bool = False
    merge_authorized: bool = False
    execution_authorized: bool = False
    next_machine_action: str = "SUPERVISOR_SCHEDULE_CYCLE"
    next_machine_action_executing_or_scheduled: bool = True


@dataclass
class DurableAtlasSupervisor:
    """Persistent asynchronous governor host. Owns the DAG; SDK/CLI execute workers."""

    root: Path
    backend: ExecutionBackend
    agents: CloudAgentRegistry
    runs: RunRegistry
    pool: AgentRolePool
    scheduler: DagToAgentScheduler
    auth: AuthDiscovery
    ready_provider: ReadyProvider | None = None
    poll_interval_sec: float = 2.0
    max_cycles: int | None = None
    status: SupervisorStatus = field(default_factory=SupervisorStatus)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        use_fake: bool = False,
        prefer_cli: bool = True,
        budget: BudgetConfig | None = None,
        ready_provider: ReadyProvider | None = None,
        poll_interval_sec: float = 2.0,
        max_cycles: int | None = None,
    ) -> DurableAtlasSupervisor:
        auth = discover_auth()
        record_auth_prerequisite(root, auth)
        agents = CloudAgentRegistry(root)
        runs = RunRegistry(root)
        pool = AgentRolePool(agents)
        cost = CostGuard(runs, config=budget or BudgetConfig())
        backend: ExecutionBackend
        authentic = "NONE"
        if use_fake:
            backend = FakeCursorSDKBackend(agents_reg=agents, runs_reg=runs, pool=pool)
            authentic = "FAKE_TEST_ONLY"
        elif prefer_cli and auth.cursor_api_key_available != "YES":
            # D-088: authentic local worker is cursor-agent CLI when User API key deferred.
            backend = CursorAgentCliExecutionPort(
                root=root, agents_reg=agents, runs_reg=runs, pool=pool
            )
            authentic = WorkerBackend.CURSOR_AGENT_CLI.value
        elif auth.local_sdk_available == "YES" or auth.cloud_sdk_runtime == "ENABLED":
            backend = CursorSDKExecutionBackend(
                root=root, agents_reg=agents, runs_reg=runs, pool=pool, discovery=auth
            )
            authentic = WorkerBackend.CURSOR_SDK.value
        else:
            backend = CursorAgentCliExecutionPort(
                root=root, agents_reg=agents, runs_reg=runs, pool=pool
            )
            authentic = WorkerBackend.CURSOR_AGENT_CLI.value
        scheduler = DagToAgentScheduler(
            backend=backend, agents=agents, runs=runs, pool=pool, cost=cost
        )
        status = SupervisorStatus(auth=auth, authentic_worker_backend=authentic)
        return cls(
            root=root,
            backend=backend,
            agents=agents,
            runs=runs,
            pool=pool,
            scheduler=scheduler,
            auth=auth,
            ready_provider=ready_provider,
            poll_interval_sec=poll_interval_sec,
            max_cycles=max_cycles,
            status=status,
        )

    def request_stop(self) -> None:
        self._stop.set()

    async def startup_recovery(self) -> RecoveryReport:
        report = await recover_runtime(
            backend=self.backend, agents=self.agents, runs=self.runs
        )
        self.status.last_recovery = report
        return report

    async def schedule_cycle(self) -> ScheduleCycleResult:
        ready: list[ReadyWorkItem] = []
        if self.ready_provider is not None:
            provided = self.ready_provider()
            if isinstance(provided, list):
                ready = provided
            else:
                ready = await provided
        result = await self.scheduler.cycle(ready)
        self.status.cycles += 1
        self.status.last_cycle = result
        self.status.human_scheduler_events = 0
        return result

    async def run_forever(self) -> SupervisorStatus:
        self.status.running = True
        await self.startup_recovery()
        try:
            while not self._stop.is_set():
                await self.schedule_cycle()
                if self.max_cycles is not None and self.status.cycles >= self.max_cycles:
                    break
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_interval_sec
                    )
                except TimeoutError:
                    continue
        finally:
            self.status.running = False
            close = getattr(self.backend, "aclose", None)
            if close is not None:
                maybe = close()
                if asyncio.iscoroutine(maybe):
                    await maybe
        return self.status


def status_dict(status: SupervisorStatus) -> dict[str, object]:
    auth = status.auth
    return {
        "ok": True,
        "directive_id": status.directive_id,
        "package_id": status.package_id,
        "primary_continuation_backend": status.primary_backend,
        "stop_hook_backend": status.stop_hook_backend,
        "authentic_worker_backend": status.authentic_worker_backend,
        "official_cursor_sdk_agent_runtime": (
            "DEFERRED_USER_API_KEY"
            if auth and auth.cursor_api_key_available != "YES"
            else "AVAILABLE"
        ),
        "cycles": status.cycles,
        "running": status.running,
        "cursor_api_key_available": auth.cursor_api_key_available if auth else "NO",
        "local_sdk_available": auth.local_sdk_available if auth else "NO",
        "cloud_sdk_runtime": auth.cloud_sdk_runtime if auth else "DISABLED",
        "cursor_sdk_version": auth.cursor_sdk_version if auth else None,
        "human_scheduler_events": status.human_scheduler_events,
        "owner_action_required_now": status.owner_action_required_now,
        "merge_authorized": False,
        "execution_authorized": False,
        "next_machine_action": status.next_machine_action,
        "next_machine_action_executing_or_scheduled": (
            status.next_machine_action_executing_or_scheduled
        ),
    }
