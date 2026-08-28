"""Durable agent / run registries. Evidence and routing only — never authority."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.sdk.models import (
    AGENTS_NAME,
    PLACEHOLDER_DIGEST,
    RUNS_NAME,
    STATE_DIR_RELATIVE,
    TERMINAL_RUN_STATUSES,
    AgentRecord,
    AgentRole,
    AgentState,
    RunRecord,
    RunStatus,
    SdkRuntimeError,
    _utc_now,
)


def resolve_runtime_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise SdkRuntimeError("repository root is not a directory", code="PATH_UNSAFE")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise SdkRuntimeError("refusing filesystem root or home", code="PATH_UNSAFE")
    return resolved


def runtime_store_dir(root: Path) -> Path:
    return resolve_runtime_root(root) / STATE_DIR_RELATIVE


def _write_json_atomic(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded + "\n", encoding="utf-8")
    os.replace(tmp, target)


class AgentRegistryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    agents: dict[str, AgentRecord] = Field(default_factory=dict)
    record_digest: str = Field(min_length=64, max_length=64)
    merge_authorized: bool = False
    execution_authorized: bool = False
    authority_granted: bool = False

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("record_digest")
        return payload


class RunRegistryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    runs: dict[str, RunRecord] = Field(default_factory=dict)
    by_idempotency: dict[str, str] = Field(default_factory=dict)
    record_digest: str = Field(min_length=64, max_length=64)
    merge_authorized: bool = False
    execution_authorized: bool = False
    authority_granted: bool = False

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("record_digest")
        return payload


def _seal_agents(state: AgentRegistryState) -> AgentRegistryState:
    if state.merge_authorized or state.execution_authorized or state.authority_granted:
        raise SdkRuntimeError("agent registry cannot carry authority", code="AUTHORITY_INJECTION")
    return state.model_copy(update={"record_digest": hash_payload(state.unsigned_payload())})


def _seal_runs(state: RunRegistryState) -> RunRegistryState:
    if state.merge_authorized or state.execution_authorized or state.authority_granted:
        raise SdkRuntimeError("run registry cannot carry authority", code="AUTHORITY_INJECTION")
    return state.model_copy(update={"record_digest": hash_payload(state.unsigned_payload())})


def _verify_agents(state: AgentRegistryState) -> AgentRegistryState:
    expected = hash_payload(state.unsigned_payload())
    if state.record_digest != expected:
        raise SdkRuntimeError("agent registry digest mismatch", code="STATE_CORRUPT")
    return state


def _verify_runs(state: RunRegistryState) -> RunRegistryState:
    expected = hash_payload(state.unsigned_payload())
    if state.record_digest != expected:
        raise SdkRuntimeError("run registry digest mismatch", code="STATE_CORRUPT")
    return state


def _roles_incompatible(a: AgentRole, b: AgentRole) -> bool:
    mutating = {AgentRole.IMPLEMENTER, AgentRole.REMEDIATOR}
    independent = {
        AgentRole.INDEPENDENT_VERIFIER,
        AgentRole.SECURITY_REVIEWER,
        AgentRole.READ_ONLY_ANALYST,
    }
    return (a in mutating and b in independent) or (b in mutating and a in independent)


class CloudAgentRegistry:
    """Persist cloud/local agent identities for resume and role isolation."""

    def __init__(self, root: Path) -> None:
        self.root = resolve_runtime_root(root)
        self.path = runtime_store_dir(self.root) / AGENTS_NAME

    def load(self) -> AgentRegistryState:
        if not self.path.exists():
            return _seal_agents(
                AgentRegistryState(agents={}, record_digest=PLACEHOLDER_DIGEST)
            )
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return _verify_agents(AgentRegistryState.model_validate(raw))

    def save(self, state: AgentRegistryState) -> AgentRegistryState:
        sealed = _seal_agents(state)
        _write_json_atomic(self.path, sealed.model_dump(mode="json"))
        return sealed

    def upsert(self, record: AgentRecord) -> AgentRecord:
        state = self.load()
        existing = state.agents.get(record.agent_id)
        if existing is not None and _roles_incompatible(existing.role, record.role):
            raise SdkRuntimeError(
                "incompatible role reuse of agent lineage forbidden",
                code="ROLE_LINEAGE_COLLISION",
            )
        agents = dict(state.agents)
        agents[record.agent_id] = record
        self.save(state.model_copy(update={"agents": agents}))
        return record

    def get(self, agent_id: str) -> AgentRecord | None:
        return self.load().agents.get(agent_id)

    def list_active(self, *, role: AgentRole | None = None) -> list[AgentRecord]:
        agents = self.load().agents.values()
        out = [
            a
            for a in agents
            if not a.archived
            and a.state != AgentState.ARCHIVED
            and (role is None or a.role == role)
        ]
        return sorted(out, key=lambda a: a.created_at)

    def archive(self, agent_id: str) -> AgentRecord:
        state = self.load()
        record = state.agents.get(agent_id)
        if record is None:
            raise SdkRuntimeError("unknown agent_id", code="UNKNOWN_AGENT")
        updated = record.model_copy(update={"archived": True, "state": AgentState.ARCHIVED})
        agents = dict(state.agents)
        agents[agent_id] = updated
        self.save(state.model_copy(update={"agents": agents}))
        return updated


class RunRegistry:
    """Persist every SDK run for recovery and idempotent scheduling."""

    def __init__(self, root: Path) -> None:
        self.root = resolve_runtime_root(root)
        self.path = runtime_store_dir(self.root) / RUNS_NAME

    def load(self) -> RunRegistryState:
        if not self.path.exists():
            return _seal_runs(
                RunRegistryState(runs={}, by_idempotency={}, record_digest=PLACEHOLDER_DIGEST)
            )
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return _verify_runs(RunRegistryState.model_validate(raw))

    def save(self, state: RunRegistryState) -> RunRegistryState:
        sealed = _seal_runs(state)
        _write_json_atomic(self.path, sealed.model_dump(mode="json"))
        return sealed

    def find_by_idempotency(self, key: str) -> RunRecord | None:
        state = self.load()
        run_id = state.by_idempotency.get(key)
        if run_id is None:
            return None
        return state.runs.get(run_id)

    def upsert(self, record: RunRecord) -> RunRecord:
        state = self.load()
        existing_id = state.by_idempotency.get(record.idempotency_key)
        if existing_id is not None and existing_id != record.run_id:
            existing = state.runs.get(existing_id)
            if existing is not None:
                raise SdkRuntimeError(
                    "idempotency collision with different run_id",
                    code="IDEMPOTENCY_COLLISION",
                )
        runs = dict(state.runs)
        by_key = dict(state.by_idempotency)
        runs[record.run_id] = record
        by_key[record.idempotency_key] = record.run_id
        self.save(state.model_copy(update={"runs": runs, "by_idempotency": by_key}))
        return record

    def get(self, run_id: str) -> RunRecord | None:
        return self.load().runs.get(run_id)

    def nonterminal(self) -> list[RunRecord]:
        return sorted(
            (r for r in self.load().runs.values() if r.status not in TERMINAL_RUN_STATUSES),
            key=lambda r: r.started_at,
        )

    def mark_terminal(
        self,
        run_id: str,
        *,
        status: RunStatus,
        result_digest: str,
        candidate_head: str | None = None,
        candidate_tree: str | None = None,
        token_usage_total: int | None = None,
        cost_charged_cents: float | None = None,
    ) -> RunRecord:
        if status not in TERMINAL_RUN_STATUSES:
            raise SdkRuntimeError("status is not terminal", code="BAD_STATUS")
        state = self.load()
        record = state.runs.get(run_id)
        if record is None:
            raise SdkRuntimeError("unknown run_id", code="UNKNOWN_RUN")
        if record.is_terminal and record.status == status and record.result_digest == result_digest:
            return record
        if record.is_terminal and record.result_digest != result_digest:
            raise SdkRuntimeError("malicious or conflicting result replay", code="RESULT_REPLAY")
        updated = record.model_copy(
            update={
                "status": status,
                "completed_at": _utc_now(),
                "result_digest": result_digest,
                "candidate_head": (
                    candidate_head if candidate_head is not None else record.candidate_head
                ),
                "candidate_tree": (
                    candidate_tree if candidate_tree is not None else record.candidate_tree
                ),
                "token_usage_total": token_usage_total,
                "cost_charged_cents": cost_charged_cents,
            }
        )
        runs = dict(state.runs)
        runs[run_id] = updated
        self.save(state.model_copy(update={"runs": runs}))
        return updated
