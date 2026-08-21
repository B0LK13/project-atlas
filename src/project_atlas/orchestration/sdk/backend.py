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
from project_atlas.orchestration.sdk.cloud_run_recovery import (
    CloudRunRecoveryClass,
    recover_exact_cloud_run,
)
from project_atlas.orchestration.sdk.idempotency import build_idempotency_key
from project_atlas.orchestration.sdk.lease_registry import (
    require_scheduler_lease,
    resolve_durable_lease,
)
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
from project_atlas.orchestration.sdk.mutation_attribution import (
    CloudRemoteGitAttributionProvider,
    RunGitInfo,
    collect_run_changed_paths,
    extract_terminal_run_git,
    load_run_mutation_baseline,
    mint_cloud_run_baseline,
    persist_agent_remote_high_water,
    persist_run_mutation_baseline,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.result_adapter import adapt_run_result, normalize_run_status
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    GovernorLease,
    WorkerBackend,
    WorkerLineage,
    bind_worker_lineage,
    enforce_allowed_paths,
    load_run_pre_head,
    mint_creation_sequence,
    persist_run_pre_head,
    require_changed_paths_determined,
    require_creation_sequence,
)


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
        self._leases: dict[str, GovernorLease] = {}
        self._pre_heads: dict[str, str | None] = {}
        self._cloud_attribution = CloudRemoteGitAttributionProvider()

    def register_lease(self, lease: GovernorLease) -> None:
        self._leases[lease.lease_id] = lease

    def register_cloud_attribution_provider(
        self, provider: CloudRemoteGitAttributionProvider
    ) -> None:
        """Test/injection hook for remote head/diff resolvers."""
        self._cloud_attribution = provider

    def _git_rev_parse_head(self) -> str | None:
        """Pin HEAD before a mutating run so commits cannot hide from the delta."""
        import subprocess

        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        head = (completed.stdout or "").strip()
        return head if len(head) >= 7 else None

    def _require_mutating_lease(self, request: ScheduleRequest) -> GovernorLease | None:
        if request.role not in MUTATING_ROLES:
            return None
        lease = require_scheduler_lease(self.root, request, invocation=True)
        if lease is None:
            raise SdkRuntimeError(
                "mutating lease missing after reload",
                code="LEASE_REQUIRED",
            )
        self._leases[lease.lease_id] = lease
        return lease

    def _lineage_from_stored(self, stored: AgentRecord) -> WorkerLineage:
        if (
            stored.workspace is None
            or stored.repository is None
            or stored.creation_generation is None
            or stored.worker_backend is None
        ):
            raise SdkRuntimeError(
                "agent registry missing lineage",
                code="LINEAGE_MISSING",
            )
        sequence = require_creation_sequence(
            self.root, stored.agent_id, stored.creation_sequence
        )
        return WorkerLineage(
            identity=stored.agent_id,
            backend=WorkerBackend(stored.worker_backend),
            workspace=stored.workspace,
            repository=stored.repository,
            package_id=stored.package_id,
            role=stored.role,
            branch=stored.branch or CANONICAL_BRANCH,
            base_main=stored.base_main,
            creation_generation=stored.creation_generation,
            creation_sequence=sequence,
        )

    def _bind_lineage(
        self,
        *,
        agent_id: str,
        request: ScheduleRequest,
        expected: WorkerLineage | None = None,
        creation_sequence: int | None = None,
    ) -> WorkerLineage:
        sequence = creation_sequence
        if sequence is None and expected is not None:
            sequence = expected.creation_sequence
        if sequence is None:
            sequence = 1
        return bind_worker_lineage(
            identity=agent_id,
            backend=WorkerBackend.CURSOR_SDK,
            workspace=str(self.root.resolve()),
            repository=CANONICAL_REPO_URL,
            package_id=request.package_id,
            role=request.role,
            branch=request.branch or CANONICAL_BRANCH,
            base_main=request.base_main,
            creation_generation=request.dag_generation,
            creation_sequence=sequence,
            expected=expected,
        )

    def _resolve_pre_head(self, run_id: str) -> str | None:
        """Actual pre-run HEAD only. Never substitute candidate_head."""
        if run_id in self._pre_heads:
            return self._pre_heads[run_id]
        return load_run_pre_head(self.root, run_id)

    def _resolve_mutating_runtime(
        self,
        record: RunRecord,
        *,
        stored_agent: AgentRecord | None,
        agent_runtime: AgentRuntime | None,
        git_info: RunGitInfo | None,
    ) -> AgentRuntime:
        """Never default a cloud-shaped mutating run to LOCAL worktree proof.

        ORCH-SDK-CLOUD-MUTATING-ATTRIBUTION-001: a missing agent row plus
        Run.git (or a `bc-` identity) must fail closed. Assuming LOCAL would
        accept a clean local worktree and hide the remote Cloud delta.
        Historical D106/D112 local tests without a registry row remain LOCAL
        only when the run is not cloud-shaped.
        """
        if agent_runtime is not None:
            return agent_runtime
        if stored_agent is not None:
            return stored_agent.runtime
        if git_info is not None or record.agent_id.startswith("bc-"):
            raise SdkRuntimeError(
                "mutating wait_run missing agent runtime",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        return AgentRuntime.LOCAL

    def _enforce_run_paths(
        self,
        record: RunRecord,
        *,
        terminal_git: Any = None,
        agent_runtime: AgentRuntime | None = None,
    ) -> None:
        if record.role not in MUTATING_ROLES:
            return
        lease = None
        if record.lease_id:
            lease = self._leases.get(record.lease_id) or resolve_durable_lease(
                self.root, record.lease_id
            )
        if lease is None:
            raise SdkRuntimeError(
                "mutating wait_run missing lease",
                code="LEASE_REQUIRED",
            )
        stored_agent = self.agents_reg.get(record.agent_id)
        git_info = (
            extract_terminal_run_git(terminal_git)
            if terminal_git is not None
            else None
        )
        runtime = self._resolve_mutating_runtime(
            record,
            stored_agent=stored_agent,
            agent_runtime=agent_runtime,
            git_info=git_info,
        )
        attribution = None
        local_pre_head = None
        if runtime == AgentRuntime.CLOUD:
            attribution = load_run_mutation_baseline(self.root, record.run_id)
            if attribution is None:
                raise SdkRuntimeError(
                    "missing CLOUD run mutation baseline",
                    code="REMOTE_ATTRIBUTION_UNDETERMINED",
                )
        else:
            local_pre_head = self._resolve_pre_head(record.run_id)
        changed = collect_run_changed_paths(
            self.root,
            runtime=runtime,
            attribution=attribution,
            terminal_git=git_info,
            local_pre_head=local_pre_head,
            cloud_provider=self._cloud_attribution,
        )
        determined = require_changed_paths_determined(changed)
        try:
            enforce_allowed_paths(
                changed_paths=determined,
                allowed_paths=lease.allowed_paths,
            )
        except SdkRuntimeError as exc:
            raise SdkRuntimeError(
                f"REJECTED_SCOPE_ESCAPE: {exc}",
                code="REJECTED_SCOPE_ESCAPE",
            ) from exc
        if (
            runtime == AgentRuntime.CLOUD
            and attribution is not None
            and attribution.remote_post_head
        ):
            persist_run_mutation_baseline(self.root, attribution)
            persist_agent_remote_high_water(
                self.root, record.agent_id, attribution.remote_post_head
            )
            # Persist discovered Cloud auto-branch onto agent for follow-up lineage.
            if (
                stored_agent is not None
                and attribution.remote_branch
                and stored_agent.branch != attribution.remote_branch
            ):
                self.agents_reg.upsert(
                    stored_agent.model_copy(
                        update={"branch": attribution.remote_branch}
                    )
                )

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from cursor_sdk import AsyncClient

        from project_atlas.orchestration.sdk.windows_bridge import (
            apply_windows_discovery_patch,
            official_bridge_command,
        )

        apply_windows_discovery_patch()
        command = official_bridge_command()
        if command is None:
            self._client = await AsyncClient.launch_bridge(workspace=str(self.root))
        else:
            self._client = await AsyncClient.launch_bridge(
                command, workspace=str(self.root)
            )
        return self._client

    async def _discover_model(self, client: Any) -> str | None:
        try:
            listing = await client.models.list()
        except Exception:
            return None
        ids: list[str] = []
        items = getattr(listing, "items", listing)
        if isinstance(items, list):
            for row in items:
                ident = getattr(row, "id", None)
                if ident is None and isinstance(row, dict):
                    ident = row.get("id")
                if ident:
                    ids.append(str(ident))
        for preferred in ("composer-2.5", "composer-2", "auto-smart"):
            if preferred in ids:
                return preferred
        return ids[0] if ids else None

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

        self._require_mutating_lease(request)

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
        model = request.model or DEFAULT_MODEL
        if runtime == AgentRuntime.LOCAL:
            discovered = await self._discover_model(client)
            if discovered:
                model = discovered
        kwargs: dict[str, Any] = {
            "model": model,
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
        lineage = self._bind_lineage(
            agent_id=agent_id,
            request=request,
            creation_sequence=mint_creation_sequence(self.root, agent_id),
        )
        record = AgentRecord(
            agent_id=agent_id,
            runtime=runtime,
            role=request.role,
            package_id=request.package_id,
            base_main=request.base_main,
            branch=request.branch,
            created_at=_utc_now(),
            state=AgentState.BUSY,
            worker_backend=WorkerBackend.CURSOR_SDK.value,
            workspace=lineage.workspace,
            repository=lineage.repository,
            creation_generation=lineage.creation_generation,
            creation_sequence=lineage.creation_sequence,
            lineage_id=f"lin-{agent_id}-{lineage.creation_generation}",
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
        self._require_mutating_lease(request)
        stored = self.agents_reg.get(agent_id)
        if stored is None:
            stored = await self.resume_agent(agent_id)
        stored_lineage = self._lineage_from_stored(stored)
        self._bind_lineage(
            agent_id=agent_id,
            request=request,
            expected=stored_lineage,
            creation_sequence=stored_lineage.creation_sequence,
        )
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
        pre_head = self._git_rev_parse_head()
        send_kwargs: dict[str, Any] = {"idempotency_key": key}
        run = await agent.send(request.prompt, **send_kwargs)
        run_id = str(getattr(run, "id", None) or run.run_id)
        self._pre_heads[run_id] = pre_head
        persist_run_pre_head(self.root, run_id, pre_head)
        if stored.runtime == AgentRuntime.CLOUD and request.role in MUTATING_ROLES:
            mint_cloud_run_baseline(
                root=self.root,
                run_id=run_id,
                agent_id=stored.agent_id,
                base_main=request.base_main,
                branch=request.branch or stored.branch,
                dag_generation=request.dag_generation,
                lease_id=request.lease_id,
                package_id=request.package_id,
            )
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
        stored = self.agents_reg.get(agent_id)
        if stored is None:
            raise SdkRuntimeError("resumed agent not in registry", code="FOREIGN_AGENT")
        stored_lineage = self._lineage_from_stored(stored)
        bind_worker_lineage(
            identity=agent_id,
            backend=WorkerBackend(
                stored.worker_backend or WorkerBackend.CURSOR_SDK.value
            ),
            workspace=str(self.root.resolve()),
            repository=CANONICAL_REPO_URL,
            package_id=stored.package_id,
            role=stored.role,
            branch=stored.branch or CANONICAL_BRANCH,
            base_main=stored.base_main,
            creation_generation=stored.creation_generation or 0,
            creation_sequence=stored_lineage.creation_sequence,
            expected=stored_lineage,
        )
        from cursor_sdk import AgentOptions

        client = await self._ensure_client()
        opts: dict[str, Any] = {}
        if self._api_key:
            opts["api_key"] = self._api_key
        agent = await client.agents.resume(
            agent_id, AgentOptions(**opts) if opts else AgentOptions()
        )
        self._handles[agent_id] = agent
        return stored

    def _agent_run_options(self, *, agent_id: str) -> dict[str, Any] | None:
        """Runtime options for get_run / list_runs.

        Cloud GetRun requires ``agent_id`` + ``runtime=\"cloud\"`` (D-122 probe).
        ``api_key`` alone is insufficient. Local agents keep api_key-only opts.
        """
        stored = self.agents_reg.get(agent_id)
        cloudish = agent_id.startswith("bc-") or (
            stored is not None and stored.runtime == AgentRuntime.CLOUD
        )
        if cloudish:
            from project_atlas.orchestration.sdk.cloud_run_recovery import (
                cloud_get_run_options,
            )

            return cloud_get_run_options(agent_id=agent_id, api_key=self._api_key)
        if self._api_key:
            return {"api_key": self._api_key}
        return None

    async def get_run_status(self, run_id: str, *, agent_id: str) -> RunStatus:
        client = await self._ensure_client()
        run = await client.agents.get_run(
            run_id, self._agent_run_options(agent_id=agent_id)
        )
        status = normalize_run_status(str(getattr(run, "status", None)))
        stored = self.runs_reg.get(run_id)
        if stored is not None and stored.agent_id != agent_id:
            raise SdkRuntimeError("run/agent binding mismatch", code="BINDING_MISMATCH")
        return status

    def _terminalize_after_attribution(
        self,
        *,
        run_id: str,
        agent_id: str,
        status: RunStatus,
        result_digest: str,
        token_usage_total: int | None = None,
        terminal_git: Any = None,
        agent_runtime: AgentRuntime | None = None,
    ) -> RunRecord:
        """ONE D-119/D-115 funnel: enforce attribution BEFORE durable mark_terminal."""
        provisional = self.runs_reg.get(run_id)
        if provisional is None:
            raise SdkRuntimeError("run missing before path enforce", code="RUN_MISSING")
        if provisional.agent_id != agent_id:
            raise SdkRuntimeError("run/agent binding mismatch", code="BINDING_MISMATCH")
        # Path enforce + HW persist must precede mark_terminal.
        self._enforce_run_paths(
            provisional, terminal_git=terminal_git, agent_runtime=agent_runtime
        )
        updated = self.runs_reg.mark_terminal(
            run_id,
            status=status,
            result_digest=result_digest,
            token_usage_total=token_usage_total,
        )
        stored = self.agents_reg.get(agent_id)
        if stored is not None:
            self.agents_reg.upsert(
                stored.model_copy(update={"state": AgentState.IDLE})
            )
        return updated

    async def recover_exact_cloud_run(
        self, *, agent_id: str, run_id: str
    ) -> Any:
        """Public recovery primitive — never mark_terminal."""
        stored_agent = self.agents_reg.get(agent_id)
        stored_run = self.runs_reg.get(run_id)
        if stored_agent is None or stored_run is None:
            raise SdkRuntimeError(
                "missing persisted agent/run for recovery",
                code=CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
            )
        client = await self._ensure_client()

        async def _resume(aid: str) -> None:
            await self.resume_agent(aid)

        recovered = await recover_exact_cloud_run(
            client=client,
            agent=stored_agent,
            run=stored_run,
            agent_id=agent_id,
            run_id=run_id,
            api_key=self._api_key,
            resume=_resume,
        )
        return recovered

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
            return self._terminalize_after_attribution(
                run_id=run_id,
                agent_id=agent_id,
                status=ingested.status,
                result_digest=ingested.result_digest,
                token_usage_total=ingested.token_usage_total,
                terminal_git=result,
            )
        # Detached recovery path — exact Cloud reattach when possible
        stored = self.runs_reg.get(run_id)
        if stored is None:
            raise SdkRuntimeError("run missing before path enforce", code="RUN_MISSING")
        if stored.agent_id != agent_id:
            raise SdkRuntimeError("run/agent binding mismatch", code="BINDING_MISMATCH")
        stored_agent = self.agents_reg.get(agent_id)
        terminal_git: Any = None
        detached_status: RunStatus | None = None
        if (
            stored_agent is not None
            and stored_agent.runtime == AgentRuntime.CLOUD
            and agent_id.startswith("bc-")
        ):
            try:
                recovered = await self.recover_exact_cloud_run(
                    agent_id=agent_id, run_id=run_id
                )
                terminal_git = recovered.snapshot
                detached_status = normalize_run_status(
                    str(getattr(recovered.snapshot, "status", None) or "finished")
                )
            except SdkRuntimeError as exc:
                # Undetermined recovery: keep NONTERMINAL; never mark_terminal.
                if exc.code in {
                    CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
                    CloudRunRecoveryClass.AMBIGUOUS_RECOVERED_RUN.value,
                    CloudRunRecoveryClass.FOREIGN_RECOVERED_RUN.value,
                }:
                    raise
                raise
        else:
            detached_status = await self.get_run_status(run_id, agent_id=agent_id)
            if detached_status in {
                RunStatus.FINISHED,
                RunStatus.ERROR,
                RunStatus.CANCELLED,
            }:
                try:
                    client = await self._ensure_client()
                    terminal_git = await client.agents.get_run(
                        run_id, self._agent_run_options(agent_id=agent_id)
                    )
                except Exception:
                    terminal_git = None
        if detached_status is None or detached_status not in {
            RunStatus.FINISHED,
            RunStatus.ERROR,
            RunStatus.CANCELLED,
        }:
            return stored
        ingested = adapt_run_result(
            run_id=run_id, agent_id=agent_id, status=detached_status
        )
        return self._terminalize_after_attribution(
            run_id=run_id,
            agent_id=agent_id,
            status=ingested.status,
            result_digest=ingested.result_digest,
            terminal_git=terminal_git,
        )
