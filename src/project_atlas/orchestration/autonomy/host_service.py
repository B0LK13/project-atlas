"""Long-lived governor host. Survives launcher and worker session exit.

Returns only on explicit stop, safety stop, or unrecoverable host failure.
WAITING_OWNER is a parked runtime state, not process termination.

HOST_IS_SECOND_GOVERNOR = NO
"""

from __future__ import annotations

import json
import os
import time
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.autonomy.broker import (
    BrokerError,
    BrokerOutcome,
    ContinuationBroker,
)
from project_atlas.orchestration.autonomy.continuation import select_next
from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AgentCapability,
    ExecutionHostClass,
    NodeState,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.mutating_transport import (
    MutatingExecutionPort,
    MutatingLeaseBinding,
    MutatingRole,
    MutatingTransportError,
    ProcessMutatingBackend,
    ProcessReadOnlyBackend,
    WorkerBackendType,
    WorkerQuestionClass,
    classify_worker_question,
    cloud_api_key_present,
    compose_worker_prompt,
    local_cursor_cli_present,
    pid_is_running,
    require_active_lease,
)
from project_atlas.orchestration.autonomy.trust import require_full_pin
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

HOST_PACKAGE_ID: Final[Literal["AS-ORCH-CONTINUATION-BROKER-001"]] = (
    "AS-ORCH-CONTINUATION-BROKER-001"
)
STATE_DIR_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "host"
CURRENT_NAME: Final[str] = "current.json"
PID_NAME: Final[str] = "service.pid"
STOP_NAME: Final[str] = "stop.requested"
LOCK_NAME: Final[str] = ".host.lock"
PLACEHOLDER_DIGEST: Final[str] = "0" * 64
AUTHENTIC_BACKEND_REQUEST_ID: Final[str] = "AUTHENTIC-MUTATING-BACKEND-001"


class HostError(ValueError):
    code = "HOST_FAILED_CLOSED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class HostStopReason(StrEnum):
    EXPLICIT_STOP = "EXPLICIT_STOP"
    SAFETY_STOP = "SAFETY_STOP"
    UNRECOVERABLE = "UNRECOVERABLE"


class HostServiceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-CONTINUATION-BROKER-001"] = HOST_PACKAGE_ID
    repository_identity: str = Field(min_length=1, max_length=256)
    main_sha: str = Field(min_length=40, max_length=40)
    main_tree: str = Field(min_length=40, max_length=40)
    dag_generation: int = Field(default=0, ge=0, le=1_000_000)
    backend_type: WorkerBackendType = WorkerBackendType.NONE
    active_package_id: str | None = None
    active_lease_id: str | None = None
    cloud_agent_id: str | None = None
    cloud_run_id: str | None = None
    local_session_id: str | None = None
    process_agent_id: str | None = None
    process_run_id: str | None = None
    branch: str | None = None
    parked_owner: bool = False
    authentic_backend_request_emitted: bool = False
    completed_package_ids: tuple[str, ...] = ()
    merge_authorized: Literal[False] = False
    record_digest: str = Field(min_length=64, max_length=64)

    @field_validator("main_sha", "main_tree")
    @classmethod
    def _pin(cls, value: str) -> str:
        return require_full_pin(value, "host pin")

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("record_digest")
        return payload


def seal_host_state(state: HostServiceState) -> HostServiceState:
    return state.model_copy(update={"record_digest": hash_payload(state.unsigned_payload())})


def verify_host_state(state: HostServiceState) -> HostServiceState:
    if state.record_digest != hash_payload(state.unsigned_payload()):
        raise HostError("host state digest mismatch", code="STATE_CORRUPT")
    return state


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _store_path(store: Path, name: str) -> Path:
    if ".." in Path(name).parts or Path(name).is_absolute():
        raise HostError("host store path is unsafe", code="PATH_UNSAFE")
    target = (store / name).resolve()
    if not _inside(store.resolve(), target):
        raise HostError("host store path escapes root", code="PATH_UNSAFE")
    if (store / name).exists() and (store / name).is_symlink():
        raise HostError("symlink host state is forbidden", code="SYMLINK_STATE")
    return target


def persist_host_state(store: Path, state: HostServiceState) -> HostServiceState:
    sealed = verify_host_state(seal_host_state(state))
    store.mkdir(parents=True, exist_ok=True)
    lock = _store_path(store, LOCK_NAME)
    try:
        with ProjectIdentityLock(lock, wait_seconds=2.0, stale_seconds=30.0):
            path = _store_path(store, CURRENT_NAME)
            encoded = json.dumps(sealed.model_dump(mode="json"), sort_keys=True, indent=2)
            tmp = path.with_name(f".{path.name}.tmp")
            tmp.write_text(encoded + "\n", encoding="utf-8")
            os.replace(tmp, path)
    except IdentityLockError as exc:
        raise HostError("host lock is held", code="SERVICE_DOUBLE_START") from exc
    return sealed


def load_host_state(store: Path) -> HostServiceState:
    path = _store_path(store, CURRENT_NAME)
    if not path.is_file():
        raise HostError("host state is missing", code="STATE_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HostError("host state is unreadable", code="STATE_CORRUPT") from exc
    if not isinstance(payload, dict):
        raise HostError("host state is schema-invalid", code="STATE_CORRUPT")
    try:
        state = HostServiceState.model_validate(payload)
    except Exception as exc:
        raise HostError("host state is schema-invalid", code="STATE_CORRUPT") from exc
    return verify_host_state(state)


def request_stop(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    _store_path(store, STOP_NAME).write_text("STOP\n", encoding="utf-8")


def stop_requested(store: Path) -> bool:
    return (store / STOP_NAME).is_file()


def node_wants_mutation(node: WorkNode) -> bool:
    caps = set(node.agent_capabilities_required)
    return bool(caps & {AgentCapability.IMPLEMENT, AgentCapability.REMEDIATE})


class DurableHostService:
    """OS-durable supervisor over one ContinuationBroker and worker ports."""

    def __init__(
        self,
        *,
        governor: AutonomousGovernor,
        broker: ContinuationBroker,
        store: Path,
        root: Path,
        trusted: TrustedAnchorRecord,
        mutating: MutatingExecutionPort | None = None,
        readonly: MutatingExecutionPort | None = None,
        force_mutating: bool = False,
        poll_seconds: float = 0.05,
        owner_backoff_seconds: float = 0.05,
        expected_repository_identity: str = CANONICAL_REPOSITORY_IDENTITY,
        claim_pid: bool = True,
    ) -> None:
        if trusted.repository_identity != expected_repository_identity:
            raise HostError("cross-project host reuse is forbidden", code="CROSS_PROJECT")
        self._governor = governor
        self._broker = broker
        self._store = store
        self._root = root
        self._trusted = trusted
        worker_root = root / ".atlas" / "orchestration" / "workers"
        self._mutating = mutating or ProcessMutatingBackend(
            root=root,
            store=worker_root / "mutating",
        )
        self._readonly = readonly or ProcessReadOnlyBackend(
            root=root,
            store=worker_root / "readonly",
        )
        self._force_mutating = force_mutating
        self._poll_seconds = poll_seconds
        self._owner_backoff = owner_backoff_seconds
        snapshot = governor.snapshot()
        if not store.exists() or not (store / CURRENT_NAME).is_file():
            persist_host_state(
                store,
                HostServiceState(
                    repository_identity=expected_repository_identity,
                    main_sha=snapshot.current_main,
                    main_tree=snapshot.current_tree,
                    backend_type=_selected_backend(),
                    record_digest=PLACEHOLDER_DIGEST,
                ),
            )
        self._state = load_host_state(store)
        if self._state.repository_identity != expected_repository_identity:
            raise HostError("foreign project host state", code="FOREIGN_PROJECT")
        if claim_pid:
            _claim_pid(store)

    @property
    def state(self) -> HostServiceState:
        return self._state

    def _save(self, **updates: object) -> HostServiceState:
        self._state = persist_host_state(self._store, self._state.model_copy(update=updates))
        return self._state

    def run(self) -> HostStopReason:
        try:
            while True:
                if stop_requested(self._store):
                    return HostStopReason.EXPLICIT_STOP
                try:
                    self._step()
                except HostError as exc:
                    if exc.code == "SAFETY_STOP":
                        return HostStopReason.SAFETY_STOP
                    raise
                except BrokerError as exc:
                    if exc.code in {"SAFETY_BOUNDARY", "STATE_CORRUPT"}:
                        return HostStopReason.SAFETY_STOP
                    raise
        finally:
            _clear_pid(self._store)

    def recover_active_worker(self) -> None:
        agent_id = self._state.cloud_agent_id or self._state.process_agent_id
        run_id = self._state.cloud_run_id or self._state.process_run_id
        if agent_id is None or run_id is None:
            return
        port = self._port_for_package(self._state.active_package_id)
        receipt = port.recover(agent_id, run_id)
        if receipt.status in {"CREATING", "RUNNING"}:
            self._save(
                cloud_agent_id=(
                    receipt.agent_id
                    if receipt.backend is WorkerBackendType.CLOUD_API
                    else self._state.cloud_agent_id
                ),
                cloud_run_id=(
                    receipt.run_id
                    if receipt.backend is WorkerBackendType.CLOUD_API
                    else self._state.cloud_run_id
                ),
                process_agent_id=(
                    receipt.agent_id
                    if receipt.backend is WorkerBackendType.PROCESS
                    else self._state.process_agent_id
                ),
                process_run_id=(
                    receipt.run_id
                    if receipt.backend is WorkerBackendType.PROCESS
                    else self._state.process_run_id
                ),
            )
            return
        self._ingest_worker(receipt.status)

    def handle_worker_question(self, text: str) -> WorkerQuestionClass:
        classified = classify_worker_question(text)
        if classified is WorkerQuestionClass.ROUTINE_NEXT_STEP:
            self._auto_follow_up(text)
        # OWNER_AUTHORITY_REQUIRED is intercepted here. It is not Batch-B and
        # is not forwarded as a new owner prompt.
        return classified

    def _auto_follow_up(self, text: str) -> None:
        agent_id = self._state.cloud_agent_id or self._state.process_agent_id
        if agent_id is None:
            return
        port = self._port_for_package(self._state.active_package_id)
        receipt = port.follow_up(agent_id, compose_worker_prompt(text))
        self._save(
            process_agent_id=(
                receipt.agent_id
                if receipt.backend is WorkerBackendType.PROCESS
                else self._state.process_agent_id
            ),
            process_run_id=(
                receipt.run_id
                if receipt.backend is WorkerBackendType.PROCESS
                else self._state.process_run_id
            ),
            cloud_agent_id=(
                receipt.agent_id
                if receipt.backend is WorkerBackendType.CLOUD_API
                else self._state.cloud_agent_id
            ),
            cloud_run_id=(
                receipt.run_id
                if receipt.backend is WorkerBackendType.CLOUD_API
                else self._state.cloud_run_id
            ),
        )

    def _step(self) -> None:
        if self._state.cloud_run_id or self._state.process_run_id:
            self.recover_active_worker()
            if self._state.cloud_run_id or self._state.process_run_id:
                time.sleep(self._poll_seconds)
                return
        snapshot = self._governor.snapshot()
        decision = select_next(snapshot.nodes, hard_blockers=snapshot.hard_blockers)
        if decision.next_package_id is not None:
            node = next(
                item for item in snapshot.nodes if item.package_id == decision.next_package_id
            )
            external = node.execution_host_class is ExecutionHostClass.EXTERNAL_AGENT
            if self._force_mutating or external:
                self._launch_worker(node)
                return
        result = self._broker.run_one_cycle()
        if result.outcome is BrokerOutcome.CONTINUE:
            return
        if result.outcome is BrokerOutcome.WAITING_RESULT:
            time.sleep(self._poll_seconds)
            return
        if result.outcome is BrokerOutcome.WAITING_OWNER:
            self._save(parked_owner=True)
            time.sleep(self._owner_backoff)
            return
        if result.outcome is BrokerOutcome.SAFETY_STOP:
            raise HostError("host observed safety stop", code="SAFETY_STOP")
        if result.outcome is BrokerOutcome.HARD_BLOCKED:
            time.sleep(self._owner_backoff)
            return
        if result.outcome is BrokerOutcome.COMPLETE:
            time.sleep(self._poll_seconds)
            return

    def _launch_worker(self, node: WorkNode) -> None:
        mutating = self._force_mutating or node_wants_mutation(node)
        port = self._mutating if mutating else self._readonly
        role = MutatingRole.IMPLEMENTER
        if AgentCapability.REMEDIATE in node.agent_capabilities_required:
            role = MutatingRole.REMEDIATOR
        if not mutating:
            role = MutatingRole.IMPLEMENTER
        snapshot = self._governor.snapshot()
        agent_id = self._capable_agent(node)
        lease = self._governor.lease(
            node.package_id,
            agent_id,
            branch=f"cursor/gov-{node.package_id.lower()}",
            worktree=f"workers/{node.package_id}",
        )
        allowed = node.mutation_surface.paths or (
            ("implemented.txt",) if mutating else ("verified.txt",)
        )
        binding = MutatingLeaseBinding(
            package_id=node.package_id,
            lease_id=lease.lease_id,
            dispatch_id=f"mut-{lease.lease_id}",
            cycle_id=self._broker.state.current_cycle_id or "BRKCYC-00000000",
            repository_identity=self._state.repository_identity,
            base_main=snapshot.current_main,
            role=role,
            allowed_paths=allowed,
            branch=lease.branch,
            worktree=lease.worktree,
        )
        require_active_lease(self._governor.snapshot().leases, binding)
        try:
            receipt = port.start(binding, compose_worker_prompt(node.objective))
        except MutatingTransportError as exc:
            if exc.code in {
                "API_UNAVAILABLE",
                "API_401",
                "API_403",
                "LOCAL_AGENT_ABSENT",
                "LOCAL_AGENT_UNAUTHENTICATED",
            }:
                self._emit_backend_prerequisite()
                time.sleep(self._owner_backoff)
                return
            raise
        self._save(
            active_package_id=node.package_id,
            active_lease_id=lease.lease_id,
            backend_type=receipt.backend,
            cloud_agent_id=(
                receipt.agent_id if receipt.backend is WorkerBackendType.CLOUD_API else None
            ),
            cloud_run_id=(
                receipt.run_id if receipt.backend is WorkerBackendType.CLOUD_API else None
            ),
            process_agent_id=(
                receipt.agent_id if receipt.backend is WorkerBackendType.PROCESS else None
            ),
            process_run_id=(
                receipt.run_id if receipt.backend is WorkerBackendType.PROCESS else None
            ),
            branch=lease.branch,
            dag_generation=self._state.dag_generation + 1,
        )

    def _ingest_worker(self, status: str) -> None:
        package_id = self._state.active_package_id
        if package_id is None:
            self._clear_worker()
            return
        node = self._live_node(package_id)
        if status == "FINISHED":
            if node.state is NodeState.LEASED:
                self._governor.transition(package_id, NodeState.ACTIVE, "HOST_WORKER_STARTED")
                node = self._live_node(package_id)
            if node.state is NodeState.ACTIVE:
                self._governor.transition(package_id, NodeState.VERIFYING, "HOST_WORKER_FINISHED")
            self._governor.complete_verification(package_id, passed=True)
            completed = (*self._state.completed_package_ids, package_id)
            self._clear_worker(completed_package_ids=completed)
            return
        if status == "ERROR" and node.state is NodeState.LEASED:
            self._governor.transition(package_id, NodeState.BLOCKED, "HOST_WORKER_ERROR")
        self._clear_worker()

    def _clear_worker(self, **extra: object) -> None:
        self._save(
            active_package_id=None,
            active_lease_id=None,
            cloud_agent_id=None,
            cloud_run_id=None,
            process_agent_id=None,
            process_run_id=None,
            **extra,
        )

    def _emit_backend_prerequisite(self) -> None:
        if self._state.authentic_backend_request_emitted:
            return
        self._broker.observe_owner_gate(
            gate_id=AUTHENTIC_BACKEND_REQUEST_ID,
            current_main=self._state.main_sha,
            candidate_head=self._state.main_sha,
            candidate_tree=self._state.main_tree,
            requested_authority_class="F_MATERIAL_EXTERNAL_SPEND",
        )
        self._save(authentic_backend_request_emitted=True)

    def _live_node(self, package_id: str) -> WorkNode:
        for item in self._governor.snapshot().nodes:
            if item.package_id == package_id:
                return item
        raise HostError(f"unknown package {package_id}", code="UNKNOWN_NODE")

    def _capable_agent(self, node: WorkNode) -> str:
        required = set(node.agent_capabilities_required)
        for agent in self._governor.snapshot().agents:
            if agent.available and required <= set(agent.capabilities):
                return agent.agent_id
        raise HostError("no capable agent for package", code="AGENT_UNAVAILABLE")

    def _port_for_package(self, package_id: str | None) -> MutatingExecutionPort:
        if package_id is None:
            return self._mutating
        node = self._live_node(package_id)
        if self._force_mutating or node_wants_mutation(node):
            return self._mutating
        return self._readonly


def _selected_backend() -> WorkerBackendType:
    if cloud_api_key_present():
        return WorkerBackendType.CLOUD_API
    if local_cursor_cli_present():
        return WorkerBackendType.LOCAL_AGENT
    return WorkerBackendType.PROCESS


def _claim_pid(store: Path) -> None:
    existing = read_service_pid(store)
    if existing is not None and (existing == os.getpid() or pid_is_running(existing)):
        raise HostError("governor service already running", code="SERVICE_DOUBLE_START")
    _write_pid(store)


def _write_pid(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    _store_path(store, PID_NAME).write_text(f"{os.getpid()}\n", encoding="utf-8")


def _clear_pid(store: Path) -> None:
    path = store / PID_NAME
    if path.is_file():
        path.unlink()


def read_service_pid(store: Path) -> int | None:
    path = store / PID_NAME
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
