"""Durable Atlas supervisor — persistent host process for SDK continuation.

Does not exit for CHECKPOINT_CONTINUE, RESOURCE_YIELD, CI/IV/ADV pending,
worker terminal, or owner-gate on one branch while independent work exists.
"""

from __future__ import annotations

import asyncio
import time
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
from project_atlas.orchestration.sdk.external_observers import (
    load_observer_registry,
    nearest_wake_at,
)
from project_atlas.orchestration.sdk.host import stop_requested
from project_atlas.orchestration.sdk.models import (
    DIRECTIVE_ID,
    PACKAGE_ID,
    PRIMARY_BACKEND,
    STOP_HOOK_BACKEND,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.nonblocking_scheduler import (
    bounded_sleep_seconds,
    scheduler_tick,
)
from project_atlas.orchestration.sdk.recovery import RecoveryReport, recover_runtime
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.result_plane import (
    ingest_pending_against_registry,
    persist_result_quarantine,
    transport_state,
)
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
    last_cycle_error: str | None = None
    contained_failures: int = 0


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
            backend=backend,
            agents=agents,
            runs=runs,
            pool=pool,
            cost=cost,
            root=root,
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
            backend=self.backend,
            agents=self.agents,
            runs=self.runs,
            root=self.root,
        )
        self.status.last_recovery = report
        if report.safety_stop:
            self.status.next_machine_action = "SAFETY_STOP_HOST_ROLLBACK"
            self.status.owner_action_required_now = False
        return report

    async def schedule_cycle(self) -> ScheduleCycleResult:
        # D-092 cycle order: refresh (via ready_provider) → ingest result plane →
        # validate → consume → recover runs → recompute ready → dispatch.
        backend = WorkerBackend.CURSOR_AGENT_CLI
        if isinstance(self.backend, CursorSDKExecutionBackend):
            backend = WorkerBackend.CURSOR_SDK
        try:
            ingest_pending_against_registry(
                self.root, runs=self.runs, worker_backend=backend
            )
        except SdkRuntimeError as exc:
            persist_result_quarantine(self.root, code=exc.code, detail=str(exc))
            self.status.last_cycle_error = exc.code
            self.status.contained_failures += 1
            self.status.next_machine_action = f"RESULT_QUARANTINED:{exc.code}"
        if self.status.last_recovery and self.status.last_recovery.safety_stop:
            self.status.cycles += 1
            return ScheduleCycleResult()
        ready: list[ReadyWorkItem] = []
        if self.ready_provider is not None:
            try:
                provided = self.ready_provider()
                if isinstance(provided, list):
                    ready = provided
                else:
                    ready = await provided
            except (TimeoutError, OSError, SdkRuntimeError) as exc:
                code = getattr(exc, "code", None) or type(exc).__name__
                persist_result_quarantine(
                    self.root, code=f"READY_PROVIDER:{code}", detail=str(exc)
                )
                self.status.last_cycle_error = str(code)
                self.status.contained_failures += 1
                ready = []
        result = await self.scheduler.cycle(ready)
        self.status.cycles += 1
        self.status.last_cycle = result
        self.status.human_scheduler_events = 0
        # D-128: nonblocking liveness tick — pending externals never block ready work.
        try:
            scheduler_tick(
                self.root,
                ready=ready,
                capacity=max(1, len(ready)),
                running_workers=len(result.started),
            )
        except (TimeoutError, OSError, SdkRuntimeError, ValueError) as exc:
            code = getattr(exc, "code", None) or type(exc).__name__
            persist_result_quarantine(
                self.root,
                code=f"NONBLOCKING_TICK:{code}",
                detail=str(exc),
            )
            self.status.contained_failures += 1
        if transport_state(self.root) == "CLOSED":
            self.status.next_machine_action = "RESULT_PLANE_CONSUMED"
        return result

    async def run_forever(self) -> SupervisorStatus:
        self.status.running = True
        await self.startup_recovery()
        try:
            while not self._stop.is_set():
                if stop_requested(self.root):
                    self._stop.set()
                    break
                try:
                    await self.schedule_cycle()
                except asyncio.CancelledError:
                    raise
                except (TimeoutError, OSError, SdkRuntimeError) as exc:
                    code = getattr(exc, "code", None) or type(exc).__name__
                    if code in {"HOST_ROLLBACK_REJECTED"}:
                        self.status.next_machine_action = "SAFETY_STOP_HOST_ROLLBACK"
                        persist_result_quarantine(
                            self.root, code=str(code), detail=str(exc)
                        )
                        self.status.contained_failures += 1
                        self.status.last_cycle_error = str(code)
                        break
                    persist_result_quarantine(
                        self.root, code=str(code), detail=str(exc)
                    )
                    self.status.last_cycle_error = str(code)
                    self.status.contained_failures += 1
                    self.status.cycles += 1
                if self.max_cycles is not None and self.status.cycles >= self.max_cycles:
                    break
                # D-128: sleep only until nearest observer wake (capped). Never long CI wait.
                registry = load_observer_registry(self.root)
                wake = nearest_wake_at(registry)
                timeout = bounded_sleep_seconds(
                    next_wake_at=wake,
                    now=time.time(),
                    cap_sec=max(self.poll_interval_sec, 0.1),
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=timeout)
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
