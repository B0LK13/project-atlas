"""CursorAgentCliExecutionPort — first-class governed cursor-agent CLI backend.

Authentic local worker when official SDK User API key is deferred.
Never constructs a shell from untrusted worker prose; argv is fixed + prompt arg.
Backend implementation does not confer merge/execution authority.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.sdk.idempotency import build_idempotency_key
from project_atlas.orchestration.sdk.lease_registry import (
    require_scheduler_lease,
    resolve_durable_lease,
)
from project_atlas.orchestration.sdk.models import (
    CANONICAL_REPO_URL,
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
from project_atlas.orchestration.sdk.result_adapter import adapt_run_result
from project_atlas.orchestration.sdk.result_plane import ResultEnvelope, append_result
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    BoundWorkerResult,
    GovernorLease,
    WorkerBackend,
    WorkerLineage,
    bind_worker_lineage,
    classify_transient_failure,
    collect_actual_changed_paths,
    enforce_allowed_paths,
    normalize_cli_identity,
    recovery_action,
    require_changed_paths_determined,
    require_valid_lease,
)

# Official package still primary architectural name; CLI is production-capable here.
CLI_BACKEND_NAME = "CURSOR_AGENT_CLI"


@dataclass
class _CliSession:
    agent_id: str
    session_id: str
    role: AgentRole
    package_id: str
    base_main: str
    branch: str | None
    lineage: WorkerLineage
    lease: GovernorLease | None = None
    busy_run_id: str | None = None


@dataclass
class CursorAgentCliExecutionPort:
    """Governed adapter over authenticated local `cursor-agent` / `agent` CLI."""

    root: Path
    agents_reg: CloudAgentRegistry
    runs_reg: RunRegistry
    pool: AgentRolePool
    binary: str | None = None
    timeout_sec: float = 600.0
    trust_workspace: bool = True
    _sessions: dict[str, _CliSession] = field(default_factory=dict)
    _run_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)
    _leases: dict[str, GovernorLease] = field(default_factory=dict)

    def register_lease(self, lease: GovernorLease) -> None:
        self._leases[lease.lease_id] = lease

    def _resolve_binary(self) -> str:
        if self.binary:
            return self.binary
        for name in ("cursor-agent", "agent"):
            found = shutil.which(name)
            if found:
                return found
        raise SdkRuntimeError(
            "cursor-agent CLI not found on PATH",
            code="CLI_UNAVAILABLE",
        )

    def _lease_for(self, request: ScheduleRequest) -> GovernorLease | None:
        if request.lease_id and request.lease_id in self._leases:
            return self._leases[request.lease_id]
        loaded = resolve_durable_lease(self.root, request.lease_id)
        if loaded is not None:
            self._leases[loaded.lease_id] = loaded
        return loaded

    def _require_lease(self, request: ScheduleRequest) -> GovernorLease:
        mutating = request.role in MUTATING_ROLES
        if mutating:
            lease = require_scheduler_lease(self.root, request, invocation=True)
            if lease is None:
                raise SdkRuntimeError("mutating lease missing after reload", code="LEASE_REQUIRED")
            self._leases[lease.lease_id] = lease
            return lease
        lease = self._lease_for(request)
        return require_valid_lease(
            lease,
            role=request.role,
            dag_generation=request.dag_generation,
            package_id=request.package_id,
            mutating=False,
        )

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

    def _enforce_post_run_paths(
        self,
        request: ScheduleRequest,
        lease: GovernorLease,
        *,
        pre_head: str | None = None,
    ) -> None:
        if request.role not in MUTATING_ROLES:
            return
        changed = collect_actual_changed_paths(self.root, pre_head=pre_head)
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
        )

    def _persist_agent(
        self,
        *,
        agent_id: str,
        request: ScheduleRequest,
        lineage: WorkerLineage,
        state: AgentState,
        last_run_id: str | None = None,
    ) -> AgentRecord:
        record = AgentRecord(
            agent_id=agent_id,
            runtime=AgentRuntime.LOCAL,
            role=request.role,
            package_id=request.package_id,
            base_main=request.base_main,
            branch=request.branch,
            created_at=_utc_now(),
            state=state,
            last_run_id=last_run_id,
            worker_backend=WorkerBackend.CURSOR_AGENT_CLI.value,
            workspace=lineage.workspace,
            repository=lineage.repository,
            creation_generation=lineage.creation_generation,
            lineage_id=f"lin-{agent_id}-{lineage.creation_generation}",
        )
        self.agents_reg.upsert(record)
        return record

    def _mode_flags(self, role: AgentRole) -> list[str]:
        if role in MUTATING_ROLES:
            return ["--force"] if self.trust_workspace else []
        # Independent IV/ADV: read-only ask mode.
        return ["--mode", "ask"]

    def _build_argv(
        self,
        *,
        prompt: str,
        resume_session: str | None,
        role: AgentRole,
    ) -> list[str]:
        # Fixed argv construction — never interpolate untrusted prose into a shell.
        bin_path = self._resolve_binary()
        argv = [
            bin_path,
            "--print",
            "--output-format",
            "json",
            *self._mode_flags(role),
        ]
        if self.trust_workspace:
            argv.append("--trust")
        if resume_session:
            argv.extend(["--resume", resume_session])
        argv.append(prompt)
        return argv

    async def _invoke(
        self,
        *,
        prompt: str,
        resume_session: str | None,
        role: AgentRole,
    ) -> dict[str, Any]:
        argv = self._build_argv(prompt=prompt, resume_session=resume_session, role=role)
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self.root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_sec
                )
            except TimeoutError as exc:
                proc.kill()
                await proc.wait()
                kind = classify_transient_failure(exc)
                raise SdkRuntimeError(
                    f"CLI timeout ({recovery_action(kind)})",
                    code="TRANSIENT_TIMEOUT",
                ) from exc
        except FileNotFoundError as exc:
            raise SdkRuntimeError("CLI binary missing", code="CLI_UNAVAILABLE") from exc
        except OSError as exc:
            kind = classify_transient_failure(exc)
            action = recovery_action(kind)
            raise SdkRuntimeError(
                f"CLI bridge failure ({action})",
                code="TRANSIENT_CLI_BRIDGE",
            ) from exc

        stdout = (stdout_b or b"").decode("utf-8", errors="replace").strip()
        stderr = (stderr_b or b"").decode("utf-8", errors="replace").strip()
        if proc.returncode not in (0, None) and not stdout:
            kind = classify_transient_failure(stderr or f"exit={proc.returncode}")
            if recovery_action(kind) == "PARK_BACKOFF":
                raise SdkRuntimeError(
                    f"transient CLI failure: {stderr[:200]}",
                    code="TRANSIENT_CLI_BRIDGE",
                )
            raise SdkRuntimeError(
                f"CLI failed: {stderr[:400] or stdout[:400]}",
                code="CLI_FAILED",
            )
        payload = self._parse_json_result(stdout, stderr=stderr)
        return payload

    @staticmethod
    def _parse_json_result(stdout: str, *, stderr: str) -> dict[str, Any]:
        if not stdout:
            raise SdkRuntimeError(
                f"empty CLI output: {stderr[:200]}",
                code="CLI_EMPTY_RESULT",
            )
        # Prefer last JSON object line (stream-json may emit multiple).
        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        last_err: Exception | None = None
        for candidate in reversed(lines):
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue
            if isinstance(data, dict):
                return data
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            last_err = exc
        raise SdkRuntimeError(
            f"unparseable CLI JSON: {stdout[:200]}",
            code="CLI_BAD_JSON",
        ) from last_err

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

        lease = self._require_lease(request)
        pre_head = self._git_rev_parse_head()
        payload = await self._invoke(
            prompt=request.prompt,
            resume_session=None,
            role=request.role,
        )
        raw_session = str(payload.get("session_id") or "")
        if not raw_session:
            raise SdkRuntimeError("CLI result missing session_id", code="CLI_NO_SESSION")
        agent_id = normalize_cli_identity(raw_session)
        lineage = bind_worker_lineage(
            identity=agent_id,
            backend=WorkerBackend.CURSOR_AGENT_CLI,
            workspace=str(self.root.resolve()),
            repository=CANONICAL_REPO_URL,
            package_id=request.package_id,
            role=request.role,
            branch=request.branch or CANONICAL_BRANCH,
            base_main=request.base_main,
            creation_generation=request.dag_generation,
        )
        session = _CliSession(
            agent_id=agent_id,
            session_id=raw_session.lower(),
            role=request.role,
            package_id=request.package_id,
            base_main=request.base_main,
            branch=request.branch,
            lineage=lineage,
            lease=lease,
        )
        self._sessions[agent_id] = session
        self._persist_agent(
            agent_id=agent_id,
            request=request,
            lineage=lineage,
            state=AgentState.BUSY,
        )
        self._enforce_post_run_paths(request, lease, pre_head=pre_head)
        return self._finalize_run(session, request, key, payload)

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
        lease = self._require_lease(request)
        stored = self.agents_reg.get(agent_id)
        if stored is None:
            raise SdkRuntimeError("foreign CLI session", code="FOREIGN_IDENTITY")
        if stored.role != request.role:
            raise SdkRuntimeError("role change requires new session", code="ROLE_CHANGE")
        session = self._sessions.get(agent_id)
        if session is None:
            # Resume after supervisor restart: use AUTHORITATIVE stored lineage.
            stored_lineage = self._lineage_from_stored(stored)
            bind_worker_lineage(
                identity=agent_id,
                backend=WorkerBackend.CURSOR_AGENT_CLI,
                workspace=str(self.root.resolve()),
                repository=CANONICAL_REPO_URL,
                package_id=request.package_id,
                role=request.role,
                branch=request.branch or CANONICAL_BRANCH,
                base_main=request.base_main,
                creation_generation=request.dag_generation,
                expected=stored_lineage,
            )
            session = _CliSession(
                agent_id=agent_id,
                session_id=agent_id.removeprefix("cli-"),
                role=stored.role,
                package_id=stored.package_id,
                base_main=stored.base_main,
                branch=stored.branch,
                lineage=stored_lineage,
                lease=lease,
            )
            self._sessions[agent_id] = session
        else:
            bind_worker_lineage(
                identity=agent_id,
                backend=WorkerBackend.CURSOR_AGENT_CLI,
                workspace=str(self.root.resolve()),
                repository=CANONICAL_REPO_URL,
                package_id=request.package_id,
                role=request.role,
                branch=request.branch or CANONICAL_BRANCH,
                base_main=request.base_main,
                creation_generation=request.dag_generation,
                expected=session.lineage,
            )
        session.lease = lease
        pre_head = self._git_rev_parse_head()
        payload = await self._invoke(
            prompt=request.prompt,
            resume_session=session.session_id,
            role=request.role,
        )
        returned = str(payload.get("session_id") or session.session_id).lower()
        if returned != session.session_id and normalize_cli_identity(returned) != agent_id:
            raise SdkRuntimeError("session identity drift", code="FOREIGN_IDENTITY")
        self._enforce_post_run_paths(request, lease, pre_head=pre_head)
        return self._finalize_run(session, request, key, payload)

    def _finalize_run(
        self,
        session: _CliSession,
        request: ScheduleRequest,
        key: str,
        payload: dict[str, Any],
    ) -> RunRecord:
        run_id = str(payload.get("request_id") or payload.get("run_id") or uuid.uuid4())
        # Registry token charset: keep UUID run ids.
        if not re_fullmatch_id(run_id):
            run_id = f"cli-run-{uuid.uuid4()}"
        text = str(payload.get("result") or payload.get("text") or "")
        is_error = bool(payload.get("is_error")) or str(payload.get("subtype", "")) == "error"
        status = RunStatus.ERROR if is_error else RunStatus.FINISHED
        ingested = adapt_run_result(
            run_id=run_id,
            agent_id=session.agent_id,
            status=status,
            result_text=text,
            git_metadata={
                "head": request.candidate_head,
                "tree": request.candidate_tree,
            },
        )
        prompt_digest = hash_payload({"prompt": request.prompt})
        now = _utc_now()
        record = RunRecord(
            run_id=run_id,
            agent_id=session.agent_id,
            cycle_id=request.cycle_id,
            package_id=request.package_id,
            lease_id=request.lease_id,
            role=request.role,
            prompt_digest=prompt_digest,
            idempotency_key=key,
            status=status,
            started_at=now,
            completed_at=now,
            result_digest=ingested.result_digest,
            candidate_head=request.candidate_head,
            candidate_tree=request.candidate_tree,
            node_id=request.node_id,
            dag_generation=request.dag_generation,
            attempt=request.attempt,
        )
        self.runs_reg.upsert(record)
        self._run_payloads[run_id] = payload
        session.busy_run_id = None
        stored = self.agents_reg.get(session.agent_id)
        if stored is not None:
            self.agents_reg.upsert(
                stored.model_copy(
                    update={"last_run_id": run_id, "state": AgentState.IDLE}
                )
            )
        self._publish_result_plane(session=session, request=request, record=record, text=text)
        return record

    def _publish_result_plane(
        self,
        *,
        session: _CliSession,
        request: ScheduleRequest,
        record: RunRecord,
        text: str,
    ) -> None:
        """Independent/review roles must traverse the governed result plane."""
        if request.role not in {
            AgentRole.CLOUD_RUNTIME_AUDITOR,
            AgentRole.INDEPENDENT_VERIFIER,
            AgentRole.SECURITY_REVIEWER,
        }:
            return
        if not record.lease_id or not record.node_id or not record.result_digest:
            return
        source: Literal["IV", "ADV", "CLOUD_RUNTIME_AUDITOR"]
        if request.role == AgentRole.CLOUD_RUNTIME_AUDITOR:
            source = "CLOUD_RUNTIME_AUDITOR"
        elif request.role == AgentRole.INDEPENDENT_VERIFIER:
            source = "IV"
        else:
            source = "ADV"
        envelope_payload = _extract_structured_payload(text)
        if request.role == AgentRole.CLOUD_RUNTIME_AUDITOR:
            assignment_id = None
            for token in request.prompt.split():
                if token.startswith("assignment_id="):
                    assignment_id = token.split("=", 1)[1].strip().rstrip(".")
                    break
            if assignment_id:
                envelope_payload.setdefault("ASSIGNMENT_ID", assignment_id)
            envelope_payload.setdefault(
                "AUDIT_RESULT",
                envelope_payload.get("AUDIT_RESULT") or "FAIL",
            )
            envelope_payload.setdefault(
                "SIX_P1_RUNTIME_OPEN_COUNT",
                envelope_payload.get("SIX_P1_RUNTIME_OPEN_COUNT", 1),
            )
        binding = BoundWorkerResult(
            worker_backend=WorkerBackend.CURSOR_AGENT_CLI,
            session_or_agent_id=session.agent_id,
            run_id=record.run_id,
            package_id=record.package_id,
            dag_node=record.node_id,
            dag_generation=record.dag_generation,
            role=request.role,
            lease_id=record.lease_id,
            attempt=record.attempt,
            result_digest=record.result_digest,
            candidate_head=record.candidate_head,
            candidate_tree=record.candidate_tree,
        )
        append_result(
            self.root,
            ResultEnvelope(source=source, binding=binding, payload=envelope_payload),
        )

    async def resume_agent(self, agent_id: str) -> AgentRecord:
        stored = self.agents_reg.get(agent_id)
        if stored is None:
            raise SdkRuntimeError("foreign CLI session", code="FOREIGN_IDENTITY")
        lineage = self._lineage_from_stored(stored)
        bind_worker_lineage(
            identity=agent_id,
            backend=WorkerBackend(
                stored.worker_backend or WorkerBackend.CURSOR_AGENT_CLI.value
            ),
            workspace=str(self.root.resolve()),
            repository=CANONICAL_REPO_URL,
            package_id=stored.package_id,
            role=stored.role,
            branch=stored.branch or CANONICAL_BRANCH,
            base_main=stored.base_main,
            creation_generation=stored.creation_generation or 0,
            expected=lineage,
        )
        if agent_id not in self._sessions:
            self._sessions[agent_id] = _CliSession(
                agent_id=agent_id,
                session_id=agent_id.removeprefix("cli-"),
                role=stored.role,
                package_id=stored.package_id,
                base_main=stored.base_main,
                branch=stored.branch,
                lineage=lineage,
            )
        return stored

    async def get_run_status(self, run_id: str, *, agent_id: str) -> RunStatus:
        stored = self.runs_reg.get(run_id)
        if stored is None:
            return RunStatus.UNKNOWN
        if stored.agent_id != agent_id:
            raise SdkRuntimeError("run/agent binding mismatch", code="BINDING_MISMATCH")
        return stored.status

    async def wait_run(self, run_id: str, *, agent_id: str) -> RunRecord:
        stored = self.runs_reg.get(run_id)
        if stored is None:
            raise SdkRuntimeError("unknown run", code="FOREIGN_RESULT")
        if stored.agent_id != agent_id:
            raise SdkRuntimeError("run/agent binding mismatch", code="BINDING_MISMATCH")
        return stored


def _extract_structured_payload(text: str) -> dict[str, Any]:
    """Best-effort JSON object extraction from CLI worker prose."""
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(stripped[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def re_fullmatch_id(value: str) -> bool:
    from project_atlas.orchestration.sdk.models import _ID_RE

    return bool(_ID_RE.fullmatch(value))
