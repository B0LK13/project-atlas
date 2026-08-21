"""DAG-to-agent scheduler. Parks transient failures; never exits primary loop."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from project_atlas.orchestration.sdk.backend import ExecutionBackend
from project_atlas.orchestration.sdk.cost_guard import CostGuard
from project_atlas.orchestration.sdk.lease_registry import require_scheduler_lease
from project_atlas.orchestration.sdk.models import (
    STATE_DIR_RELATIVE,
    AgentRole,
    RunRecord,
    ScheduleRequest,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.security_gates import (
    TransientClass,
    classify_transient_failure,
    recovery_action,
)

PARKED_NAME = "scheduler-parked.json"
TRANSIENT_CODES = frozenset(
    {
        "TRANSIENT_TIMEOUT",
        "TRANSIENT_CLI_BRIDGE",
        "RATE_LIMIT",
        "NETWORK",
        "TIMEOUT",
        "SERVER_5XX",
        "CLI_BRIDGE",
    }
)


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
    lease_rejections: list[str] = field(default_factory=list)
    mutating_no_lease_backend_calls: int = 0
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
    root: Path | None = None

    def _park_path(self) -> Path | None:
        if self.root is None:
            return None
        return self.root / STATE_DIR_RELATIVE / PARKED_NAME

    def _load_parked(self) -> dict[str, object]:
        path = self._park_path()
        if path is None or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_parked(self, payload: dict[str, object]) -> None:
        path = self._park_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _is_parked(self, node_id: str) -> bool:
        parked = self._load_parked()
        entry = parked.get(node_id)
        if not isinstance(entry, dict):
            return False
        next_retry = float(entry.get("next_retry_at") or 0)
        return time.time() < next_retry

    def _park_node(self, node_id: str, *, code: str, attempt: int) -> None:
        parked = self._load_parked()
        delay = min(300.0, 2.0 ** min(attempt, 8))
        parked[node_id] = {
            "code": code,
            "attempt": attempt,
            "next_retry_at": time.time() + delay,
            "parked_at": time.time(),
        }
        self._save_parked(parked)

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
            if self._is_parked(item.node_id):
                result.parked.append(item.node_id)
                continue
            if not self.cost.allow_schedule(item.role, optional=item.optional):
                result.parked.append(item.node_id)
                continue
            if not self.pool.has_capacity(item.role) and not item.prefer_followup:
                result.parked.append(item.node_id)
                continue
            try:
                require_scheduler_lease(self.root, item, invocation=True)
            except SdkRuntimeError as exc:
                self._park_node(item.node_id, code=exc.code, attempt=item.attempt)
                result.parked.append(item.node_id)
                result.lease_rejections.append(f"{item.node_id}:{exc.code}")
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
            except (TimeoutError, OSError) as exc:
                code = (
                    "TRANSIENT_TIMEOUT"
                    if isinstance(exc, TimeoutError)
                    else "TRANSIENT_CLI_BRIDGE"
                )
                wrapped = SdkRuntimeError(
                    f"backend {type(exc).__name__}",
                    code=code,
                )
                self._park_node(item.node_id, code=wrapped.code, attempt=item.attempt)
                result.parked.append(item.node_id)
                continue
            except SdkRuntimeError as exc:
                if exc.code == "AGENT_BUSY" and existing is not None and existing.last_run_id:
                    bound = await self.backend.wait_run(
                        existing.last_run_id, agent_id=existing.agent_id
                    )
                    result.ingested.append(bound)
                    continue
                kind = classify_transient_failure(exc)
                if exc.code in TRANSIENT_CODES or kind != TransientClass.NOT_TRANSIENT:
                    action = recovery_action(kind)
                    if action == "PARK_BACKOFF":
                        self._park_node(item.node_id, code=exc.code, attempt=item.attempt)
                        result.parked.append(item.node_id)
                        continue
                    if action == "TRY_OTHER_BACKEND":
                        # Mark parked; supervisor may switch backends. No owner prompt.
                        self._park_node(
                            item.node_id,
                            code="AUTH_PERSISTENT_TRY_OTHER_BACKEND",
                            attempt=item.attempt,
                        )
                        result.parked.append(item.node_id)
                        continue
                # Non-transient: park as diagnostic, keep supervisor alive.
                self._park_node(
                    item.node_id,
                    code=f"INTERNAL_DIAGNOSTIC:{exc.code}",
                    attempt=item.attempt,
                )
                result.parked.append(item.node_id)
        return result

    async def cycle(self, ready: list[ReadyWorkItem]) -> ScheduleCycleResult:
        ingested = await self.ingest_completions()
        started = await self.assign_and_start(ready)
        started.ingested = ingested + started.ingested
        return started
