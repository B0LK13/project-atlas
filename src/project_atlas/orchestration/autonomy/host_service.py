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
    AgentLease,
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
HIGH_WATER_NAME: Final[str] = "high-water.json"
PID_NAME: Final[str] = "service.pid"
STOP_NAME: Final[str] = "stop.requested"
LOCK_NAME: Final[str] = ".host.lock"
PLACEHOLDER_DIGEST: Final[str] = "0" * 64
AUTHENTIC_BACKEND_REQUEST_ID: Final[str] = "AUTHENTIC-MUTATING-BACKEND-001"
_PARKABLE_TRANSPORT: Final[frozenset[str]] = frozenset(
    {
        "API_UNAVAILABLE",
        "API_401",
        "API_403",
        "API_NETWORK",
        "API_429",
        "LOCAL_AGENT_ABSENT",
        "LOCAL_AGENT_UNAUTHENTICATED",
    }
)


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
    pending_iv_package_id: str | None = None
    active_worker_kind: str | None = None
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


def _read_high_water(store: Path) -> tuple[int, int]:
    path = store / HIGH_WATER_NAME
    if not path.is_file():
        return 0, 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HostError("host high-water is unreadable", code="STATE_CORRUPT") from exc
    if not isinstance(payload, dict):
        raise HostError("host high-water is schema-invalid", code="STATE_CORRUPT")
    try:
        return int(payload.get("dag_generation", 0)), int(payload.get("completed_count", 0))
    except (TypeError, ValueError) as exc:
        raise HostError("host high-water is schema-invalid", code="STATE_CORRUPT") from exc


def _reject_rollback(store: Path, state: HostServiceState) -> None:
    high_gen, high_done = _read_high_water(store)
    if state.dag_generation < high_gen:
        raise HostError("host state rollback is forbidden", code="STATE_ROLLBACK")
    if len(state.completed_package_ids) < high_done:
        raise HostError("host completion rollback is forbidden", code="STATE_ROLLBACK")


def persist_host_state(store: Path, state: HostServiceState) -> HostServiceState:
    sealed = verify_host_state(seal_host_state(state))
    store.mkdir(parents=True, exist_ok=True)
    lock = _store_path(store, LOCK_NAME)
    try:
        with ProjectIdentityLock(lock, wait_seconds=2.0, stale_seconds=30.0):
            _reject_rollback(store, sealed)
            path = _store_path(store, CURRENT_NAME)
            encoded = json.dumps(sealed.model_dump(mode="json"), sort_keys=True, indent=2)
            tmp = path.with_name(f".{path.name}.tmp")
            tmp.write_text(encoded + "\n", encoding="utf-8")
            os.replace(tmp, path)
            water = _store_path(store, HIGH_WATER_NAME)
            water.write_text(
                json.dumps(
                    {
                        "dag_generation": sealed.dag_generation,
                        "completed_count": len(sealed.completed_package_ids),
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
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
    verified = verify_host_state(state)
    _reject_rollback(store, verified)
    return verified


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
        self._mutating = mutating or _default_mutating_port(root, worker_root / "mutating")
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
        _seed_cloud_lineage(self._mutating, self._state)
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
                except MutatingTransportError as exc:
                    if _is_parkable_transport(exc.code):
                        time.sleep(self._owner_backoff)
                        continue
                    raise
        finally:
            _clear_pid(self._store)

    def recover_active_worker(self) -> None:
        agent_id = self._state.cloud_agent_id or self._state.process_agent_id
        run_id = self._state.cloud_run_id or self._state.process_run_id
        if agent_id is None or run_id is None:
            return
        port = self._port_for_package(self._state.active_package_id)
        try:
            receipt = port.recover(agent_id, run_id)
        except MutatingTransportError as exc:
            if _is_parkable_transport(exc.code):
                time.sleep(self._poll_seconds)
                return
            raise
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
        leases = self._governor.snapshot().leases
        binding = self._binding_for_active()
        if binding is not None:
            require_active_lease(leases, binding)
        try:
            receipt = port.follow_up(
                agent_id,
                compose_worker_prompt(text, binding=binding),
                leases=leases,
            )
        except MutatingTransportError as exc:
            if _is_parkable_transport(exc.code):
                time.sleep(self._poll_seconds)
                return
            raise
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
        if self._state.pending_iv_package_id is not None:
            self._launch_iv_worker(self._state.pending_iv_package_id)
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
        leases = self._governor.snapshot().leases
        require_active_lease(leases, binding)
        try:
            receipt = port.start(
                binding,
                compose_worker_prompt(node.objective, binding=binding),
                leases=leases,
            )
        except MutatingTransportError as exc:
            if _is_parkable_transport(exc.code):
                self._emit_backend_prerequisite()
                time.sleep(self._owner_backoff)
                return
            raise
        self._save(
            active_package_id=node.package_id,
            active_lease_id=lease.lease_id,
            backend_type=receipt.backend,
            active_worker_kind="MUTATING" if mutating else "VERIFY",
            pending_iv_package_id=None,
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

    def _launch_iv_worker(self, package_id: str) -> None:
        node = self._live_node(package_id)
        lease = self._active_lease()
        if lease is None:
            raise HostError("pending IV has no active lease", code="LEASE_MISSING")
        allowed = node.mutation_surface.paths or ("verified.txt",)
        binding = MutatingLeaseBinding(
            package_id=package_id,
            lease_id=lease.lease_id,
            dispatch_id=f"iv-{lease.lease_id}",
            cycle_id=self._broker.state.current_cycle_id or "BRKCYC-00000000",
            repository_identity=self._state.repository_identity,
            base_main=self._governor.snapshot().current_main,
            role=MutatingRole.IMPLEMENTER,
            allowed_paths=allowed,
            branch=lease.branch,
            worktree=lease.worktree,
        )
        leases = self._governor.snapshot().leases
        require_active_lease(leases, binding)
        try:
            receipt = self._readonly.start(
                binding,
                compose_worker_prompt(f"verify {node.objective}", binding=binding),
                leases=leases,
            )
        except MutatingTransportError as exc:
            if _is_parkable_transport(exc.code):
                time.sleep(self._owner_backoff)
                return
            raise
        self._save(
            active_package_id=package_id,
            active_lease_id=lease.lease_id,
            backend_type=receipt.backend,
            active_worker_kind="VERIFY",
            pending_iv_package_id=None,
            process_agent_id=(
                receipt.agent_id if receipt.backend is WorkerBackendType.PROCESS else None
            ),
            process_run_id=(
                receipt.run_id if receipt.backend is WorkerBackendType.PROCESS else None
            ),
            cloud_agent_id=(
                receipt.agent_id if receipt.backend is WorkerBackendType.CLOUD_API else None
            ),
            cloud_run_id=(
                receipt.run_id if receipt.backend is WorkerBackendType.CLOUD_API else None
            ),
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
            needs_independent_iv = (
                self._state.active_worker_kind == "MUTATING"
                and node.iv_requirements.certification_required
                and node.iv_requirements.implementer_cannot_verify
            )
            if needs_independent_iv:
                implementer = self._lease_agent_id()
                self._governor.route_and_verify(package_id, implementer_id=implementer)
                self._save(
                    pending_iv_package_id=package_id,
                    active_package_id=package_id,
                    active_lease_id=self._state.active_lease_id,
                    cloud_agent_id=None,
                    cloud_run_id=None,
                    process_agent_id=None,
                    process_run_id=None,
                    active_worker_kind=None,
                )
                return
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
            active_worker_kind=None,
            pending_iv_package_id=None,
            **extra,
        )

    def _active_lease(self) -> AgentLease | None:
        lease_id = self._state.active_lease_id
        if lease_id is None:
            return None
        for item in self._governor.snapshot().leases:
            if item.lease_id == lease_id and item.active:
                return item
        return None

    def _lease_agent_id(self) -> str:
        lease = self._active_lease()
        if lease is None:
            raise HostError("active lease is missing", code="LEASE_MISSING")
        return str(lease.agent_id)

    def _binding_for_active(self) -> MutatingLeaseBinding | None:
        package_id = self._state.active_package_id
        lease = self._active_lease()
        if package_id is None or lease is None:
            return None
        node = self._live_node(package_id)
        mutating = self._force_mutating or node_wants_mutation(node)
        allowed = node.mutation_surface.paths or (
            ("implemented.txt",) if mutating else ("verified.txt",)
        )
        return MutatingLeaseBinding(
            package_id=package_id,
            lease_id=lease.lease_id,
            dispatch_id=f"mut-{lease.lease_id}",
            cycle_id=self._broker.state.current_cycle_id or "BRKCYC-00000000",
            repository_identity=self._state.repository_identity,
            base_main=self._governor.snapshot().current_main,
            role=MutatingRole.IMPLEMENTER,
            allowed_paths=allowed,
            branch=lease.branch,
            worktree=lease.worktree,
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
        if self._state.active_worker_kind == "VERIFY":
            return self._readonly
        if self._state.active_worker_kind == "MUTATING":
            return self._mutating
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


def _default_mutating_port(root: Path, store: Path) -> MutatingExecutionPort:
    if cloud_api_key_present():
        from project_atlas.orchestration.autonomy.cursor_cloud import CursorCloudBackend

        return CursorCloudBackend()
    if local_cursor_cli_present():
        from project_atlas.orchestration.autonomy.local_agent import LocalAgentBackend

        return LocalAgentBackend()
    return ProcessMutatingBackend(root=root, store=store)


def _seed_cloud_lineage(port: MutatingExecutionPort, state: HostServiceState) -> None:
    bind = getattr(port, "bind_lineage", None)
    if not callable(bind):
        return
    if state.cloud_agent_id and state.active_package_id:
        bind(state.active_package_id, state.cloud_agent_id)


def _is_parkable_transport(code: str) -> bool:
    if code in _PARKABLE_TRANSPORT:
        return True
    return code.startswith("API_") and code[4:].isdigit() and int(code[4:]) >= 500


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
