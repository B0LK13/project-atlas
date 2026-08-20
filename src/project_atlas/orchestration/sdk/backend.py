"""Cursor SDK execution backend + fake for tests.

Official package: cursor-sdk. Cloud agents use CloudAgentOptions.
Local agents use LocalAgentOptions. Tool restrictions are local-only.
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.sdk.auth import AuthDiscovery, discover_auth
from project_atlas.orchestration.sdk.idempotency import build_idempotency_key
from project_atlas.orchestration.sdk.models import (
    CANONICAL_REPO_URL,
    DEFAULT_MODEL,
    MUTATING_ROLES,
    AgentRecord,
    AgentRole,
    AgentRuntime,
    AgentState,
    RunRecord,
    RunStatus,
    ScheduleRequest,
    SdkRuntimeError,
    _utc_now,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.result_adapter import adapt_run_result, normalize_run_status
from project_atlas.orchestration.sdk.role_pool import AgentRolePool


class ExecutionBackend(Protocol):
    async def create_and_send(self, request: ScheduleRequest) -> RunRecord: ...

    async def send_followup(
        self, agent_id: str, request: ScheduleRequest
    ) -> RunRecord: ...

    async def resume_agent(self, agent_id: str) -> AgentRecord: ...

    async def get_run_status(self, run_id: str, *, agent_id: str) -> RunStatus: ...

    async def wait_run(self, run_id: str, *, agent_id: str) -> RunRecord: ...


@dataclass
class _FakeAgent:
    agent_id: str
    role: AgentRole
    runtime: AgentRuntime
    package_id: str
    base_main: str
    branch: str | None
    context: list[str] = field(default_factory=list)
    busy_run_id: str | None = None


@dataclass
class FakeCursorSDKBackend:
    """In-memory SDK stand-in for unit / adversarial tests."""

    agents_reg: CloudAgentRegistry
    runs_reg: RunRegistry
    pool: AgentRolePool
    _agents: dict[str, _FakeAgent] = field(default_factory=dict)
    _run_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    _id_counter: Any = field(default_factory=lambda: itertools.count(1))
    raise_busy_once: set[str] = field(default_factory=set)
    auto_finish: bool = True

    def _next_cloud_id(self) -> str:
        return f"bc-fake{next(self._id_counter):04d}"

    def _next_local_id(self) -> str:
        return f"agent-fake{next(self._id_counter):04d}"

    def _next_run_id(self) -> str:
        return f"run-fake{next(self._id_counter):04d}"

    async def create_and_send(self, request: ScheduleRequest) -> RunRecord:
        key = build_idempotency_key(
            dag_generation=request.dag_generation,
            node_id=request.node_id,
            role=request.role,
            attempt=request.attempt,
        )
        existing = self.runs_reg.find_by_idempotency(key)
        if existing is not None:
            return existing

        if request.prefer_followup and request.existing_agent_id:
            return await self.send_followup(request.existing_agent_id, request)

        runtime = request.runtime or self.pool.preferred_runtime(request.role)
        agent_id = self._next_cloud_id() if runtime == AgentRuntime.CLOUD else self._next_local_id()
        fake = _FakeAgent(
            agent_id=agent_id,
            role=request.role,
            runtime=runtime,
            package_id=request.package_id,
            base_main=request.base_main,
            branch=request.branch,
            context=[request.prompt],
        )
        self._agents[agent_id] = fake
        record = AgentRecord(
            agent_id=agent_id,
            runtime=runtime,
            role=request.role,
            package_id=request.package_id,
            base_main=request.base_main,
            branch=request.branch,
            created_at=_utc_now(),
            state=AgentState.BUSY,
        )
        self.agents_reg.upsert(record)
        return await self._start_run(fake, request, key)

    async def send_followup(self, agent_id: str, request: ScheduleRequest) -> RunRecord:
        key = build_idempotency_key(
            dag_generation=request.dag_generation,
            node_id=request.node_id,
            role=request.role,
            attempt=request.attempt,
        )
        existing = self.runs_reg.find_by_idempotency(key)
        if existing is not None:
            return existing
        fake = self._agents.get(agent_id)
        stored = self.agents_reg.get(agent_id)
        if fake is None or stored is None:
            raise SdkRuntimeError("unknown agent for followup", code="UNKNOWN_AGENT")
        if stored.role != request.role:
            raise SdkRuntimeError("role change requires new agent", code="ROLE_CHANGE")
        if agent_id in self.raise_busy_once:
            self.raise_busy_once.discard(agent_id)
            raise SdkRuntimeError("agent busy", code="AGENT_BUSY")
        if fake.busy_run_id is not None:
            raise SdkRuntimeError("agent busy", code="AGENT_BUSY")
        fake.context.append(request.prompt)
        return await self._start_run(fake, request, key)

    async def _start_run(
        self, fake: _FakeAgent, request: ScheduleRequest, key: str
    ) -> RunRecord:
        run_id = self._next_run_id()
        fake.busy_run_id = run_id
        prompt_digest = hash_payload({"prompt": request.prompt})
        run = RunRecord(
            run_id=run_id,
            agent_id=fake.agent_id,
            cycle_id=request.cycle_id,
            package_id=request.package_id,
            lease_id=request.lease_id,
            role=request.role,
            prompt_digest=prompt_digest,
            idempotency_key=key,
            status=RunStatus.RUNNING,
            started_at=_utc_now(),
            candidate_head=request.candidate_head,
            candidate_tree=request.candidate_tree,
            node_id=request.node_id,
            dag_generation=request.dag_generation,
            attempt=request.attempt,
        )
        self.runs_reg.upsert(run)
        self.agents_reg.upsert(
            self.agents_reg.get(fake.agent_id).model_copy(  # type: ignore[union-attr]
                update={"last_run_id": run_id, "state": AgentState.BUSY}
            )
        )
        result_text = f"ok:{request.node_id}:ctx={len(fake.context)}"
        self._run_results[run_id] = {
            "status": "finished",
            "result_text": result_text,
            "context_len": len(fake.context),
        }
        if self.auto_finish:
            await self.wait_run(run_id, agent_id=fake.agent_id)
            return self.runs_reg.get(run_id)  # type: ignore[return-value]
        return run

    async def resume_agent(self, agent_id: str) -> AgentRecord:
        record = self.agents_reg.get(agent_id)
        if record is None:
            raise SdkRuntimeError("cannot resume unknown agent", code="UNKNOWN_AGENT")
        if agent_id not in self._agents:
            # Rehydrate in-memory handle after process restart.
            self._agents[agent_id] = _FakeAgent(
                agent_id=agent_id,
                role=record.role,
                runtime=record.runtime,
                package_id=record.package_id,
                base_main=record.base_main,
                branch=record.branch,
                context=["resumed"],
            )
        return record

    async def get_run_status(self, run_id: str, *, agent_id: str) -> RunStatus:
        run = self.runs_reg.get(run_id)
        if run is None or run.agent_id != agent_id:
            raise SdkRuntimeError("unknown or mismatched run", code="UNKNOWN_RUN")
        # Simulate cloud completing while the Atlas client was disconnected:
        # result metadata may exist before local registry is updated.
        meta = self._run_results.get(run_id)
        if meta is not None and not run.is_terminal:
            return normalize_run_status(str(meta.get("status", "finished")))
        return run.status

    async def wait_run(self, run_id: str, *, agent_id: str) -> RunRecord:
        run = self.runs_reg.get(run_id)
        if run is None or run.agent_id != agent_id:
            raise SdkRuntimeError("unknown or mismatched run", code="UNKNOWN_RUN")
        if run.is_terminal:
            return run
        meta = self._run_results.get(run_id, {"status": "finished", "result_text": ""})
        ingested = adapt_run_result(
            run_id=run_id,
            agent_id=agent_id,
            status=meta.get("status", "finished"),
            result_text=str(meta.get("result_text", "")),
        )
        updated = self.runs_reg.mark_terminal(
            run_id,
            status=ingested.status,
            result_digest=ingested.result_digest,
            candidate_head=ingested.candidate_head,
            candidate_tree=ingested.candidate_tree,
            token_usage_total=ingested.token_usage_total,
            cost_charged_cents=ingested.cost_charged_cents,
        )
        fake = self._agents.get(agent_id)
        if fake is not None and fake.busy_run_id == run_id:
            fake.busy_run_id = None
        stored = self.agents_reg.get(agent_id)
        if stored is not None:
            self.agents_reg.upsert(stored.model_copy(update={"state": AgentState.IDLE}))
        return updated

    def context_len(self, agent_id: str) -> int:
        fake = self._agents.get(agent_id)
        return 0 if fake is None else len(fake.context)


class CursorSDKExecutionBackend:
    """Live official cursor-sdk backend (async)."""

    def __init__(
        self,
        *,
        root: Path,
        agents_reg: CloudAgentRegistry,
        runs_reg: RunRegistry,
        pool: AgentRolePool,
        discovery: AuthDiscovery | None = None,
        api_key: str | None = None,
    ) -> None:
        self.root = root
        self.agents_reg = agents_reg
        self.runs_reg = runs_reg
        self.pool = pool
        self.discovery = discovery or discover_auth()
        # Read key only into process memory; never log/persist.
        self._api_key = api_key if api_key is not None else __import__("os").environ.get(
            "CURSOR_API_KEY"
        )
        self._client: Any = None
        self._handles: dict[str, Any] = {}

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from cursor_sdk import AsyncClient

        self._client = await AsyncClient.launch_bridge(workspace=str(self.root))
        return self._client

    async def aclose(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            close = getattr(client, "aclose", None) or getattr(client, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result

    async def __aenter__(self) -> CursorSDKExecutionBackend:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def _local_tools(self, role: AgentRole) -> dict[str, Any]:
        if role in MUTATING_ROLES:
            return {}
        # Local-only tool restrictions (deny wins).
        return {
            "tools": ["read", "grep", "glob", "ls", "shell"],
            "disallowed_tools": ["write", "edit", "delete", "ApplyPatch"],
        }

    async def create_and_send(self, request: ScheduleRequest) -> RunRecord:
        key = build_idempotency_key(
            dag_generation=request.dag_generation,
            node_id=request.node_id,
            role=request.role,
            attempt=request.attempt,
        )
        existing = self.runs_reg.find_by_idempotency(key)
        if existing is not None:
            return existing
        if request.prefer_followup and request.existing_agent_id:
            return await self.send_followup(request.existing_agent_id, request)

        runtime = request.runtime or self.pool.preferred_runtime(request.role)
        if runtime == AgentRuntime.CLOUD and self.discovery.cloud_sdk_runtime != "ENABLED":
            if self.discovery.local_sdk_available == "YES":
                runtime = AgentRuntime.LOCAL
            else:
                raise SdkRuntimeError(
                    "CURSOR_SDK_AUTH_REQUIRED", code="CURSOR_SDK_AUTH_REQUIRED"
                )

        from cursor_sdk import CloudAgentOptions, CloudRepository, LocalAgentOptions

        client = await self._ensure_client()
        kwargs: dict[str, Any] = {
            "model": request.model or DEFAULT_MODEL,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if runtime == AgentRuntime.CLOUD:
            kwargs["cloud"] = CloudAgentOptions(
                repos=[
                    CloudRepository(
                        url=CANONICAL_REPO_URL,
                        starting_ref=request.base_main,
                    )
                ],
                auto_create_pr=False,
                skip_reviewer_request=True,
                metadata={
                    "atlas_package": request.package_id,
                    "atlas_role": request.role.value,
                    "atlas_node": request.node_id,
                },
            )
        else:
            local_opts: dict[str, Any] = {"cwd": str(self.root)}
            local_opts.update(self._local_tools(request.role))
            kwargs["local"] = LocalAgentOptions(**local_opts)

        agent = await client.agents.create(**kwargs)
        agent_id = str(getattr(agent, "agent_id", None) or agent.id)
        self._handles[agent_id] = agent
        record = AgentRecord(
            agent_id=agent_id,
            runtime=runtime,
            role=request.role,
            package_id=request.package_id,
            base_main=request.base_main,
            branch=request.branch,
            created_at=_utc_now(),
            state=AgentState.BUSY,
        )
        self.agents_reg.upsert(record)
        return await self._send_on_agent(agent, record, request, key)

    async def send_followup(self, agent_id: str, request: ScheduleRequest) -> RunRecord:
        key = build_idempotency_key(
            dag_generation=request.dag_generation,
            node_id=request.node_id,
            role=request.role,
            attempt=request.attempt,
        )
        existing = self.runs_reg.find_by_idempotency(key)
        if existing is not None:
            return existing
        stored = self.agents_reg.get(agent_id)
        if stored is None:
            stored = await self.resume_agent(agent_id)
        if stored.role != request.role:
            raise SdkRuntimeError("role change requires new agent", code="ROLE_CHANGE")
        agent = self._handles.get(agent_id)
        if agent is None:
            await self.resume_agent(agent_id)
            agent = self._handles[agent_id]
        try:
            return await self._send_on_agent(agent, stored, request, key)
        except Exception as exc:
            if self._is_busy(exc):
                active = stored.last_run_id
                if active:
                    return await self.wait_run(active, agent_id=agent_id)
                raise SdkRuntimeError("agent busy without bound run", code="AGENT_BUSY") from exc
            raise

    @staticmethod
    def _is_busy(exc: BaseException) -> bool:
        name = type(exc).__name__
        code = getattr(exc, "code", None)
        return name == "AgentBusyError" or code in {"agent_busy", "AGENT_BUSY"}

    async def _send_on_agent(
        self,
        agent: Any,
        stored: AgentRecord,
        request: ScheduleRequest,
        key: str,
    ) -> RunRecord:
        send_kwargs: dict[str, Any] = {"idempotency_key": key}
        run = await agent.send(request.prompt, **send_kwargs)
        run_id = str(getattr(run, "id", None) or run.run_id)
        prompt_digest = hash_payload({"prompt": request.prompt})
        record = RunRecord(
            run_id=run_id,
            agent_id=stored.agent_id,
            cycle_id=request.cycle_id,
            package_id=request.package_id,
            lease_id=request.lease_id,
            role=request.role,
            prompt_digest=prompt_digest,
            idempotency_key=key,
            status=RunStatus.RUNNING,
            started_at=_utc_now(),
            candidate_head=request.candidate_head,
            candidate_tree=request.candidate_tree,
            node_id=request.node_id,
            dag_generation=request.dag_generation,
            attempt=request.attempt,
        )
        self.runs_reg.upsert(record)
        self.agents_reg.upsert(
            stored.model_copy(update={"last_run_id": run_id, "state": AgentState.BUSY})
        )
        self._handles[f"run:{run_id}"] = run
        return record

    async def resume_agent(self, agent_id: str) -> AgentRecord:
        from cursor_sdk import AgentOptions

        stored = self.agents_reg.get(agent_id)
        if stored is None:
            raise SdkRuntimeError("resumed agent not in registry", code="FOREIGN_AGENT")
        client = await self._ensure_client()
        opts: dict[str, Any] = {}
        if self._api_key:
            opts["api_key"] = self._api_key
        agent = await client.agents.resume(
            agent_id, AgentOptions(**opts) if opts else AgentOptions()
        )
        self._handles[agent_id] = agent
        return stored

    async def get_run_status(self, run_id: str, *, agent_id: str) -> RunStatus:
        client = await self._ensure_client()
        run = await client.agents.get_run(run_id)
        status = normalize_run_status(str(getattr(run, "status", None)))
        stored = self.runs_reg.get(run_id)
        if stored is not None and stored.agent_id != agent_id:
            raise SdkRuntimeError("run/agent binding mismatch", code="BINDING_MISMATCH")
        return status

    async def wait_run(self, run_id: str, *, agent_id: str) -> RunRecord:
        handle = self._handles.get(f"run:{run_id}")
        if handle is not None:
            result = await handle.wait()
            status = normalize_run_status(str(getattr(result, "status", "finished")))
            text = getattr(result, "result", None) or getattr(result, "text", None) or ""
            usage = getattr(result, "usage", None)
            tokens = getattr(usage, "total_tokens", None) if usage is not None else None
            ingested = adapt_run_result(
                run_id=run_id,
                agent_id=agent_id,
                status=status,
                result_text=str(text) if text is not None else "",
                token_usage_total=tokens,
            )
            updated = self.runs_reg.mark_terminal(
                run_id,
                status=ingested.status,
                result_digest=ingested.result_digest,
                token_usage_total=ingested.token_usage_total,
            )
            stored = self.agents_reg.get(agent_id)
            if stored is not None:
                self.agents_reg.upsert(stored.model_copy(update={"state": AgentState.IDLE}))
            return updated
        # Detached recovery path
        status = await self.get_run_status(run_id, agent_id=agent_id)
        if status not in {RunStatus.FINISHED, RunStatus.ERROR, RunStatus.CANCELLED}:
            return self.runs_reg.get(run_id)  # type: ignore[return-value]
        ingested = adapt_run_result(run_id=run_id, agent_id=agent_id, status=status)
        return self.runs_reg.mark_terminal(
            run_id, status=ingested.status, result_digest=ingested.result_digest
        )
