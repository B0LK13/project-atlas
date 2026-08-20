"""DAG-to-agent scheduler. Uses the primary governor — no second DAG engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from project_atlas.orchestration.sdk.backend import ExecutionBackend
from project_atlas.orchestration.sdk.cost_guard import CostGuard
from project_atlas.orchestration.sdk.models import (
    AgentRole,
    RunRecord,
    ScheduleRequest,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool


@dataclass
class ReadyWorkItem:
    """Ready DAG node ready for SDK assignment. Not authority."""

    role: AgentRole
    package_id: str
    node_id: str
    cycle_id: str
    dag_generation: int
    base_main: str
    prompt: str
    lease_id: str | None = None
    branch: str | None = None
    candidate_head: str | None = None
    candidate_tree: str | None = None
    attempt: int = 1
    prefer_followup: bool = False
    existing_agent_id: str | None = None
    optional: bool = False
    critical_path_score: int = 0


@dataclass
class ScheduleCycleResult:
    started: list[RunRecord] = field(default_factory=list)
    ingested: list[RunRecord] = field(default_factory=list)
    parked: list[str] = field(default_factory=list)
    owner_gates_held: int = 0
    human_scheduler_events: int = 0
    merge_authorized: bool = False
    execution_authorized: bool = False


@dataclass
class DagToAgentScheduler:
    """Refresh → ingest → assign → start. No human micro-scheduling."""

    backend: ExecutionBackend
    agents: CloudAgentRegistry
    runs: RunRegistry
    pool: AgentRolePool
    cost: CostGuard

    async def ingest_completions(self) -> list[RunRecord]:
        ingested: list[RunRecord] = []
        for run in self.runs.nonterminal():
            status = await self.backend.get_run_status(run.run_id, agent_id=run.agent_id)
            if status.value in {"FINISHED", "ERROR", "CANCELLED"}:
                updated = await self.backend.wait_run(run.run_id, agent_id=run.agent_id)
                ingested.append(updated)
        return ingested

    async def assign_and_start(self, items: list[ReadyWorkItem]) -> ScheduleCycleResult:
        result = ScheduleCycleResult()
        ordered = sorted(items, key=lambda i: (-i.critical_path_score, i.node_id))
        for item in ordered:
            if not self.cost.allow_schedule(item.role, optional=item.optional):
                result.parked.append(item.node_id)
                continue
            if not self.pool.has_capacity(item.role) and not item.prefer_followup:
                result.parked.append(item.node_id)
                continue
            existing = None
            if item.prefer_followup or item.existing_agent_id:
                existing = self.pool.select_followup_agent(
                    role=item.role,
                    package_id=item.package_id,
                    preferred_agent_id=item.existing_agent_id,
                )
            request = ScheduleRequest(
                role=item.role,
                package_id=item.package_id,
                node_id=item.node_id,
                cycle_id=item.cycle_id,
                dag_generation=item.dag_generation,
                attempt=item.attempt,
                lease_id=item.lease_id,
                base_main=item.base_main,
                branch=item.branch,
                candidate_head=item.candidate_head,
                candidate_tree=item.candidate_tree,
                prompt=item.prompt,
                prefer_followup=existing is not None,
                existing_agent_id=existing.agent_id if existing else None,
            )
            try:
                if existing is not None:
                    run = await self.backend.send_followup(existing.agent_id, request)
                else:
                    run = await self.backend.create_and_send(request)
                result.started.append(run)
            except SdkRuntimeError as exc:
                if exc.code == "AGENT_BUSY" and existing is not None and existing.last_run_id:
                    # Reconcile: bind active run, do not spawn duplicate.
                    bound = await self.backend.wait_run(
                        existing.last_run_id, agent_id=existing.agent_id
                    )
                    result.ingested.append(bound)
                else:
                    raise
        return result

    async def cycle(self, ready: list[ReadyWorkItem]) -> ScheduleCycleResult:
        ingested = await self.ingest_completions()
        started = await self.assign_and_start(ready)
        started.ingested = ingested + started.ingested
        return started
