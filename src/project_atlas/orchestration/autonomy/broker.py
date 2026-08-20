"""AS-ORCH-CONTINUATION-BROKER-001 invocation supervisor.

Bridges the AS-ORCH-001E persistent logical loop to a SESSION_ONE_SHOT
transport by starting exactly one successor cycle after a nonterminal
checkpoint. This module is not a second governor, DAG engine, lease
engine, or dispatch authority.

CONTINUATION_BACKEND = SAME_PROCESS_SUPERVISOR_OVER_001E_WITH_001D_DISPATCHPORT
BROKER_CAN_AUTHORIZE_MERGE = NO
BROKER_CAN_GRANT_WAIVER = NO
BROKER_CAN_EXPAND_OBJECTIVE = NO
BROKER_CAN_BYPASS_OWNER_GATE = NO
BROKER_CAN_SELF_CERTIFY = NO
BROKER_CAN_OVERRIDE_GOVERNOR = NO
BROKER_IS_SECOND_GOVERNOR = NO
"""

from __future__ import annotations

import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.autonomy.continuation import select_next
from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.loop import (
    STATE_DIR_RELATIVE as LOOP_STATE_DIR_RELATIVE,
)
from project_atlas.orchestration.autonomy.loop import (
    AutonomousLoop,
    CallableDispatchPort,
    DispatchPort,
    LoopError,
    LoopPhase,
)
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    NodeState,
    OwnerGateKind,
    StopReason,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import (
    evaluate_target_moved,
    require_full_pin,
)
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

BROKER_PACKAGE_ID: Final[Literal["AS-ORCH-CONTINUATION-BROKER-001"]] = (
    "AS-ORCH-CONTINUATION-BROKER-001"
)
BROKER_DIRECTIVE_ID: Final[str] = (
    "D-AUTONOMOUS-CONTINUATION-BROKER-AND-OWNER-PROMPT-SUPPRESSION-078"
)
STATE_DIR_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "broker"
CURRENT_NAME: Final[str] = "current.json"
HIGH_WATER_NAME: Final[str] = "high-water.json"
LOCK_NAME: Final[str] = ".broker.lock"
PLACEHOLDER_DIGEST: Final[str] = "0" * 64
MAX_CYCLES_PER_RUN: Final[int] = 32
CONTINUATION_BACKEND_SELECTED: Final[str] = (
    "SAME_PROCESS_SUPERVISOR_OVER_001E_WITH_001D_DISPATCHPORT"
)
CONTINUATION_BACKEND_EVIDENCE: Final[str] = (
    "src/project_atlas/orchestration/autonomy/broker.py"
    "+ src/project_atlas/orchestration/autonomy/loop.py"
    "+ src/project_atlas/orchestration/dispatcher.py"
    " (atlas orchestrator dispatch-once / dispatch-recover)"
)

BATCH_B_OWNER_REQUEST_ID: Final[str] = "BATCH-B-CONTEXT-INTEGRATION-001"
BATCH_B_MAIN: Final[str] = "7e797468a2eca37c959920912b1fa264df4be638"
BATCH_B_HEAD: Final[str] = "e06350ea994fc9619ce786e423788d60f0057479"
BATCH_B_TREE: Final[str] = "393b21539b25842ce6d0b1b0a7c94aa00219c53b"
BATCH_B_AUTHORITY: Final[str] = OwnerGateKind.A_PROTECTED_MAIN_MERGE.value


class BrokerError(ValueError):
    """Fail-closed broker error. Not an authority grant."""

    code = "BROKER_FAILED_CLOSED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class BrokerCrash(RuntimeError):
    """Test-only crash injection after a persisted phase. Not an authority grant."""

    def __init__(self, phase: str) -> None:
        super().__init__(f"injected broker crash after {phase}")
        self.phase = phase


class BrokerOutcome(StrEnum):
    CONTINUE = "CONTINUE"
    WAITING_RESULT = "WAITING_RESULT"
    WAITING_OWNER = "WAITING_OWNER"
    HARD_BLOCKED = "HARD_BLOCKED"
    SAFETY_STOP = "SAFETY_STOP"
    COMPLETE = "COMPLETE"


class OwnerRequestRecord(BaseModel):
    """Durable owner-gate observation. Not authority and not a user prompt."""

    model_config = ConfigDict(extra="forbid")

    owner_request_id: str = Field(min_length=1, max_length=128)
    owner_gate_fingerprint: str = Field(min_length=64, max_length=64)
    request_emitted: bool
    request_emitted_seq: int = Field(ge=0, le=1_000_000)
    main_sha: str = Field(min_length=40, max_length=40)
    candidate_head: str = Field(min_length=40, max_length=40)
    candidate_tree: str = Field(min_length=40, max_length=40)
    authority_required: str = Field(min_length=1, max_length=64)
    stale: bool = False
    satisfied: bool = False

    @field_validator("main_sha", "candidate_head", "candidate_tree")
    @classmethod
    def _pin(cls, value: str) -> str:
        return require_full_pin(value, "owner-request pin")


class WorkerObservation(BaseModel):
    """Advisory worker/transport metadata. Never scheduler authority."""

    model_config = ConfigDict(extra="ignore")

    requested_transition: str | None = None
    owner_action_required: bool = False
    terminal: bool = False
    execution_authorized: bool = False
    blocker_id: str | None = None
    blocker_class: str | None = None
    evidence: str | None = None
    safe_default: str | None = None


class BrokerState(BaseModel):
    """Persisted broker runtime. Evidence identity, not owner authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-CONTINUATION-BROKER-001"] = BROKER_PACKAGE_ID
    repository_identity: str = Field(min_length=1, max_length=256)
    main_sha: str = Field(min_length=40, max_length=40)
    main_tree: str = Field(min_length=40, max_length=40)
    current_cycle_id: str | None = None
    parent_cycle_id: str | None = None
    successor_cycle_id: str | None = None
    successor_started: bool = False
    checkpoint_digest: str | None = None
    seen_checkpoint_digests: tuple[str, ...] = ()
    seen_cycle_ids: tuple[str, ...] = ()
    seen_result_digests: tuple[str, ...] = ()
    dag_generation: int = Field(default=0, ge=0, le=1_000_000)
    active_dispatch_id: str | None = None
    active_lease_id: str | None = None
    outcome: BrokerOutcome | None = None
    owner_requests: tuple[OwnerRequestRecord, ...] = ()
    owner_notification_count: int = Field(default=0, ge=0, le=1_000_000)
    invocation_count: int = Field(default=0, ge=0, le=1_000_000)
    last_result_digest: str | None = None
    last_checkpoint_replay: Literal["NONE", "IGNORED"] = "NONE"
    last_loop_phase: str | None = None
    last_stop_reason: str | None = None
    safe_work_remaining: bool = False
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    authority_granted: Literal[False] = False
    broker_is_second_governor: Literal[False] = False
    record_digest: str = Field(min_length=64, max_length=64)

    @field_validator("main_sha", "main_tree")
    @classmethod
    def _pin(cls, value: str) -> str:
        return require_full_pin(value, "broker pin")

    @model_validator(mode="after")
    def _no_authority(self) -> BrokerState:
        if (
            self.merge_authorized
            or self.execution_authorized
            or self.authority_granted
            or self.broker_is_second_governor
        ):
            raise ValueError("broker state cannot carry authority or second-governor identity")
        return self

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("record_digest")
        return payload


class BrokerCycleResult(BaseModel):
    """One supervised cycle result. Transport terminal != DAG terminal."""

    model_config = ConfigDict(extra="forbid")

    outcome: BrokerOutcome
    cycle_id: str | None = None
    successor_cycle_id: str | None = None
    checkpoint_digest: str | None = None
    checkpoint_replay: Literal["NONE", "IGNORED"] = "NONE"
    owner_prompts: int = 0
    owner_notification_count: int = 0
    dispatched: bool = False
    recovered: bool = False
    package_id: str | None = None
    worker_exited: bool = True
    primary_dag_continuation: bool = False
    human_scheduler_events: int = 0
    duplicate_dispatch: bool = False
    duplicate_successor: bool = False
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    authority_granted: Literal[False] = False
    broker_is_second_governor: Literal[False] = False


def owner_gate_fingerprint(
    *,
    gate_id: str,
    current_main: str,
    candidate_head: str,
    candidate_tree: str,
    requested_authority_class: str,
) -> str:
    return hash_payload(
        {
            "gate_id": gate_id,
            "current_main": require_full_pin(current_main, "fingerprint main"),
            "candidate_head": require_full_pin(candidate_head, "fingerprint head"),
            "candidate_tree": require_full_pin(candidate_tree, "fingerprint tree"),
            "requested_authority_class": requested_authority_class,
        }
    )


def batch_b_fingerprint() -> str:
    return owner_gate_fingerprint(
        gate_id=BATCH_B_OWNER_REQUEST_ID,
        current_main=BATCH_B_MAIN,
        candidate_head=BATCH_B_HEAD,
        candidate_tree=BATCH_B_TREE,
        requested_authority_class=BATCH_B_AUTHORITY,
    )


def seed_batch_b_owner_request() -> OwnerRequestRecord:
    return OwnerRequestRecord(
        owner_request_id=BATCH_B_OWNER_REQUEST_ID,
        owner_gate_fingerprint=batch_b_fingerprint(),
        request_emitted=True,
        request_emitted_seq=1,
        main_sha=BATCH_B_MAIN,
        candidate_head=BATCH_B_HEAD,
        candidate_tree=BATCH_B_TREE,
        authority_required=BATCH_B_AUTHORITY,
        stale=False,
        satisfied=False,
    )


def seal_broker_state(state: BrokerState) -> BrokerState:
    return state.model_copy(update={"record_digest": hash_payload(state.unsigned_payload())})


def verify_broker_state(state: BrokerState) -> BrokerState:
    expected = hash_payload(state.unsigned_payload())
    if state.record_digest != expected:
        raise BrokerError("broker state digest mismatch", code="STATE_CORRUPT")
    return state


def initial_broker_state(
    trusted: TrustedAnchorRecord,
    *,
    main_sha: str | None = None,
    main_tree: str | None = None,
) -> BrokerState:
    return seal_broker_state(
        BrokerState(
            repository_identity=trusted.repository_identity,
            main_sha=main_sha or trusted.trusted_main,
            main_tree=main_tree or trusted.trusted_tree,
            owner_requests=(seed_batch_b_owner_request(),),
            owner_notification_count=1,
            record_digest=PLACEHOLDER_DIGEST,
        )
    )


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlink(path: Path) -> None:
    if path.exists() and path.is_symlink():
        raise BrokerError("symlink state target is forbidden", code="SYMLINK_STATE")


def _store_path(root: Path, relative: str) -> Path:
    if ".." in Path(relative).parts or Path(relative).is_absolute():
        raise BrokerError("broker store path is unsafe", code="PATH_UNSAFE")
    target = (root / relative).resolve()
    if not _inside(root, target):
        raise BrokerError("broker store path escapes root", code="PATH_UNSAFE")
    _reject_symlink(root / relative)
    _reject_symlink(target)
    return target


def _write_json_atomic(target: Path, payload: dict[str, object]) -> None:
    _reject_symlink(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _read_high_water(store: Path) -> int:
    path = store / HIGH_WATER_NAME
    if not path.is_file():
        return 0
    _reject_symlink(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BrokerError("high-water mark is unreadable", code="STATE_CORRUPT") from exc
    if not isinstance(payload, dict) or "dag_generation" not in payload:
        raise BrokerError("high-water mark is schema-invalid", code="STATE_CORRUPT")
    try:
        return int(payload["dag_generation"])
    except (TypeError, ValueError) as exc:
        raise BrokerError("high-water mark is schema-invalid", code="STATE_CORRUPT") from exc


def load_broker_state(store: Path) -> BrokerState:
    path = _store_path(store, CURRENT_NAME)
    if not path.is_file():
        raise BrokerError("broker state is missing", code="STATE_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BrokerError("broker state is unreadable", code="STATE_CORRUPT") from exc
    if not isinstance(payload, dict):
        raise BrokerError("broker state is schema-invalid", code="STATE_CORRUPT")
    try:
        state = BrokerState.model_validate(payload)
    except Exception as exc:
        raise BrokerError("broker state is schema-invalid", code="STATE_CORRUPT") from exc
    verified = verify_broker_state(state)
    high_water = _read_high_water(store)
    if verified.dag_generation < high_water:
        raise BrokerError("broker state rollback is forbidden", code="STATE_ROLLBACK")
    return verified


def persist_broker_state(store: Path, state: BrokerState) -> BrokerState:
    sealed = seal_broker_state(state)
    verify_broker_state(sealed)
    root = store.resolve()
    _reject_symlink(root)
    lock_path = _store_path(root, LOCK_NAME)
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            high_water = _read_high_water(root)
            if sealed.dag_generation < high_water:
                raise BrokerError("broker state rollback is forbidden", code="STATE_ROLLBACK")
            _write_json_atomic(
                _store_path(root, CURRENT_NAME),
                sealed.model_dump(mode="json"),
            )
            _write_json_atomic(
                _store_path(root, HIGH_WATER_NAME),
                {"dag_generation": sealed.dag_generation},
            )
    except IdentityLockError as exc:
        raise BrokerError("broker lock is held", code="CONCURRENT_BROKER") from exc
    return sealed


def wire_001d_dispatch_port() -> CallableDispatchPort:
    """Reuse the landed 001D dispatcher. Does not invent a second dispatch engine."""

    def _dispatch_once(root: Path) -> dict[str, object]:
        from project_atlas.orchestration.dispatcher import run_dispatch_once

        receipt = run_dispatch_once(root=root)
        payload = receipt.to_public_dict()
        payload["digest"] = receipt.dispatch_id or ""
        return payload

    def _recover(root: Path, dispatch_id: str) -> dict[str, object]:
        from project_atlas.orchestration.dispatcher import recover_dispatch

        receipt = recover_dispatch(dispatch_id, root=root)
        payload = receipt.to_public_dict()
        payload["digest"] = receipt.dispatch_id or dispatch_id
        return payload

    return CallableDispatchPort(_dispatch_once, _recover)


def _cycle_id(generation: int) -> str:
    return f"BRKCYC-{generation:08d}"


def _ready_count(governor: AutonomousGovernor) -> int:
    return sum(1 for node in governor.snapshot().nodes if node.state is NodeState.READY)


def _safe_work_exists(governor: AutonomousGovernor) -> bool:
    snapshot = governor.snapshot()
    decision = select_next(snapshot.nodes, hard_blockers=snapshot.hard_blockers)
    return decision.next_package_id is not None


class ContinuationBroker:
    """Invocation supervisor above 001E. Never becomes a second governor."""

    def __init__(
        self,
        *,
        governor: AutonomousGovernor,
        trusted: TrustedAnchorRecord,
        store: Path,
        root: Path,
        loop_store: Path | None = None,
        dispatch: DispatchPort | None = None,
        expected_repository_identity: str = CANONICAL_REPOSITORY_IDENTITY,
        crash_after: str | None = None,
    ) -> None:
        if trusted.repository_identity != expected_repository_identity:
            raise BrokerError("cross-project broker reuse is forbidden", code="CROSS_PROJECT")
        if evaluate_target_moved(
            governor.snapshot().current_main, governor.snapshot().current_tree, trusted
        ) or governor.snapshot().target_moved:
            raise BrokerError("refusing broker on moved target", code="TARGET_MOVED")
        self._governor = governor
        self._trusted = trusted
        self._store = store
        self._root = root
        self._crash_after = crash_after
        self._dispatch = dispatch if dispatch is not None else wire_001d_dispatch_port()
        resolved_root = root.resolve()
        resolved_store = store.resolve()
        _reject_symlink(store)
        _reject_symlink(resolved_store)
        if not _inside(resolved_root, resolved_store):
            raise BrokerError("broker store path escapes root", code="PATH_UNSAFE")
        if not store.exists():
            persist_broker_state(
                store,
                initial_broker_state(
                    trusted,
                    main_sha=governor.snapshot().current_main,
                    main_tree=governor.snapshot().current_tree,
                ),
            )
        self._state = load_broker_state(store)
        if self._state.repository_identity != expected_repository_identity:
            raise BrokerError("foreign project broker state", code="FOREIGN_PROJECT")
        self._loop = AutonomousLoop(
            governor=governor,
            trusted=trusted,
            store=loop_store or (root / LOOP_STATE_DIR_RELATIVE),
            root=root,
            dispatch=self._dispatch,
            expected_repository_identity=expected_repository_identity,
        )

    @property
    def state(self) -> BrokerState:
        return self._state

    @property
    def loop(self) -> AutonomousLoop:
        return self._loop

    def _save(self, **updates: object) -> BrokerState:
        current = self._state.model_copy(update=updates)
        self._state = persist_broker_state(self._store, current)
        return self._state

    def _maybe_crash(self, phase: str) -> None:
        if self._crash_after == phase:
            raise BrokerCrash(phase)

    def authorize_merge(self) -> None:
        raise BrokerError("broker cannot authorize merge", code="AUTHORITY_DENIED")

    def grant_waiver(self) -> None:
        raise BrokerError("broker cannot grant a waiver", code="AUTHORITY_DENIED")

    def expand_objective(self) -> None:
        raise BrokerError("broker cannot expand an objective", code="AUTHORITY_DENIED")

    def bypass_owner_gate(self) -> None:
        raise BrokerError("broker cannot bypass an owner gate", code="AUTHORITY_DENIED")

    def self_certify(self) -> None:
        raise BrokerError("broker cannot self-certify", code="AUTHORITY_DENIED")

    def override_governor(self) -> None:
        raise BrokerError("broker cannot override the governor", code="AUTHORITY_DENIED")

    def observe_owner_gate(
        self,
        *,
        gate_id: str,
        current_main: str,
        candidate_head: str,
        candidate_tree: str,
        requested_authority_class: str,
    ) -> tuple[OwnerRequestRecord, int]:
        """Ingest an owner-gate observation. Notify at most once per fingerprint."""
        fingerprint = owner_gate_fingerprint(
            gate_id=gate_id,
            current_main=current_main,
            candidate_head=candidate_head,
            candidate_tree=candidate_tree,
            requested_authority_class=requested_authority_class,
        )
        existing = next(
            (item for item in self._state.owner_requests if item.owner_request_id == gate_id),
            None,
        )
        if existing is not None and existing.owner_gate_fingerprint != fingerprint:
            if (
                existing.main_sha == current_main
                and existing.candidate_head == candidate_head
                and existing.candidate_tree == candidate_tree
            ):
                raise BrokerError("owner request id collision", code="OWNER_REQUEST_COLLISION")
            replaced = existing.model_copy(update={"stale": True})
            others = tuple(
                item
                for item in self._state.owner_requests
                if item.owner_request_id != gate_id
            )
            emitted = OwnerRequestRecord(
                owner_request_id=gate_id,
                owner_gate_fingerprint=fingerprint,
                request_emitted=True,
                request_emitted_seq=self._state.owner_notification_count + 1,
                main_sha=current_main,
                candidate_head=candidate_head,
                candidate_tree=candidate_tree,
                authority_required=requested_authority_class,
            )
            self._save(
                owner_requests=(*others, replaced, emitted),
                owner_notification_count=self._state.owner_notification_count + 1,
            )
            return emitted, 1
        match = next(
            (
                item
                for item in self._state.owner_requests
                if item.owner_gate_fingerprint == fingerprint and not item.stale
            ),
            None,
        )
        if match is not None:
            return match, 0
        emitted = OwnerRequestRecord(
            owner_request_id=gate_id,
            owner_gate_fingerprint=fingerprint,
            request_emitted=True,
            request_emitted_seq=self._state.owner_notification_count + 1,
            main_sha=current_main,
            candidate_head=candidate_head,
            candidate_tree=candidate_tree,
            authority_required=requested_authority_class,
        )
        self._save(
            owner_requests=(*self._state.owner_requests, emitted),
            owner_notification_count=self._state.owner_notification_count + 1,
        )
        return emitted, 1

    def ingest_completed_cycle(
        self,
        *,
        cycle_id: str,
        checkpoint_digest: str,
        result_digest: str,
    ) -> BrokerCycleResult:
        """Replay-resistant cycle ingest. Duplicate receipts do not spawn work."""
        if cycle_id not in self._state.seen_cycle_ids and (
            self._state.current_cycle_id not in {None, cycle_id}
        ):
            raise BrokerError("forged cycle id", code="FORGED_CYCLE")
        expected = self._state.checkpoint_digest
        if expected is not None and checkpoint_digest != expected:
            if checkpoint_digest in self._state.seen_checkpoint_digests:
                self._save(last_checkpoint_replay="IGNORED")
                return self._result(
                    BrokerOutcome.CONTINUE
                    if self._state.outcome is BrokerOutcome.CONTINUE
                    else self._state.outcome or BrokerOutcome.COMPLETE,
                    checkpoint_replay="IGNORED",
                )
            raise BrokerError("forged or stale checkpoint", code="FORGED_CHECKPOINT")
        if (
            checkpoint_digest in self._state.seen_checkpoint_digests
            or result_digest in self._state.seen_result_digests
            or (
                cycle_id in self._state.seen_cycle_ids
                and self._state.successor_started
            )
        ):
            self._save(last_checkpoint_replay="IGNORED")
            return self._result(
                self._state.outcome or BrokerOutcome.COMPLETE,
                checkpoint_replay="IGNORED",
                duplicate_successor=False,
            )
        raise BrokerError("unknown cycle result", code="UNKNOWN_CYCLE_RESULT")

    def ingest_worker_observation(self, observation: WorkerObservation) -> BrokerCycleResult:
        """Worker metadata cannot seize scheduler control. Governor recomputes."""
        del observation
        if _safe_work_exists(self._governor):
            return self.run_one_cycle()
        return self.run_one_cycle()

    def observe_external_owner_transition(self, *, request_id: str) -> BrokerCycleResult:
        """Resume after a genuine external owner transition already on the DAG.

        Does not grant the gate and does not merge. The caller must have
        already applied the authorized world-state change to the governor.
        """
        updated: list[OwnerRequestRecord] = []
        found = False
        for item in self._state.owner_requests:
            if item.owner_request_id == request_id and not item.stale:
                updated.append(item.model_copy(update={"satisfied": True, "stale": True}))
                found = True
            else:
                updated.append(item)
        if not found:
            raise BrokerError("owner request is unknown", code="UNKNOWN_OWNER_REQUEST")
        self._save(
            owner_requests=tuple(updated),
            outcome=None,
            last_stop_reason=None,
        )
        self._loop.clear_owner_park_after_external_change()
        return self.run_one_cycle()

    def refresh_pins(self, *, main_sha: str, main_tree: str) -> None:
        """Observe a new main/tree. Marks unmatched owner requests stale."""
        main_sha = require_full_pin(main_sha, "refresh main")
        main_tree = require_full_pin(main_tree, "refresh tree")
        refreshed = tuple(
            item.model_copy(update={"stale": True})
            if item.main_sha != main_sha and not item.stale
            else item
            for item in self._state.owner_requests
        )
        self._save(main_sha=main_sha, main_tree=main_tree, owner_requests=refreshed)

    def run(self, *, max_cycles: int = MAX_CYCLES_PER_RUN) -> BrokerCycleResult:
        """Supervise successor cycles until a park/stop. Owner is not the scheduler."""
        last = self._result(self._state.outcome or BrokerOutcome.CONTINUE)
        for _ in range(max_cycles):
            last = self.run_one_cycle()
            if last.checkpoint_replay == "IGNORED" and last.outcome is not BrokerOutcome.CONTINUE:
                return last
            if last.outcome is BrokerOutcome.CONTINUE:
                continue
            return last
        if last.outcome is BrokerOutcome.CONTINUE and _safe_work_exists(self._governor):
            return last
        return last

    def run_one_cycle(self) -> BrokerCycleResult:
        verify_broker_state(self._state)
        if self._loop.state.phase == LoopPhase.FAILED_CLOSED:
            return self._finish(BrokerOutcome.SAFETY_STOP, recovered=True)
        in_flight = self._loop.state.phase in {
            LoopPhase.LEASED,
            LoopPhase.DISPATCHING,
            LoopPhase.AWAITING_RESULT,
            LoopPhase.VALIDATING,
        }
        if in_flight:
            loop_result = self._loop.recover()
            self._maybe_crash(loop_result.phase.value)
            return self._classify(loop_result, recovered=True, fresh_cycle=False)

        if (
            self._state.outcome is BrokerOutcome.CONTINUE
            and self._state.successor_cycle_id is not None
            and not self._state.successor_started
        ):
            return self._start_successor()

        if (
            self._loop.state.phase == LoopPhase.STOPPED
            and self._loop.state.stop_reason is StopReason.RESOURCE_BOUNDARY
            and _safe_work_exists(self._governor)
        ):
            self._loop.begin_fresh_invocation()
            return self._start_successor(resource_yield=True)

        if self._loop.state.phase == LoopPhase.STOPPED and not _safe_work_exists(self._governor):
            return self._classify_stopped()

        return self._start_successor()

    def _start_successor(self, *, resource_yield: bool = False) -> BrokerCycleResult:
        if (
            self._state.successor_cycle_id is not None
            and self._state.successor_started
            and self._state.current_cycle_id == self._state.successor_cycle_id
        ):
            return self._result(
                self._state.outcome or BrokerOutcome.COMPLETE,
                checkpoint_replay="IGNORED",
                duplicate_successor=False,
            )
        if resource_yield or self._loop.state.ticks_in_invocation:
            try:
                self._loop.begin_fresh_invocation()
            except LoopError as exc:
                if exc.code == "SAFETY_BOUNDARY":
                    return self._finish(BrokerOutcome.SAFETY_STOP)
                raise
        parent = self._state.current_cycle_id
        generation = self._state.dag_generation + 1
        cycle_id = _cycle_id(generation)
        if cycle_id in self._state.seen_cycle_ids:
            raise BrokerError("successor replay is forbidden", code="SUCCESSOR_REPLAY")
        self._save(
            parent_cycle_id=parent,
            current_cycle_id=cycle_id,
            successor_cycle_id=None,
            successor_started=True,
            dag_generation=generation,
            invocation_count=self._state.invocation_count + 1,
            last_checkpoint_replay="NONE",
        )
        loop_result = self._loop.tick()
        self._maybe_crash(loop_result.phase.value)
        return self._classify(loop_result, recovered=False, fresh_cycle=True)

    def _classify_stopped(self) -> BrokerCycleResult:
        reason = self._loop.state.stop_reason
        if reason is StopReason.OWNER_GATE:
            prompts = self._park_owner_from_governor()
            return self._finish(BrokerOutcome.WAITING_OWNER, owner_prompts=prompts)
        if reason is StopReason.HARD_BLOCKER:
            return self._finish(BrokerOutcome.HARD_BLOCKED)
        if reason is StopReason.SAFETY_BOUNDARY:
            return self._finish(BrokerOutcome.SAFETY_STOP)
        if reason is StopReason.RESOURCE_BOUNDARY and _safe_work_exists(self._governor):
            self._loop.begin_fresh_invocation()
            return self._start_successor(resource_yield=True)
        if reason in {StopReason.NO_ELIGIBLE_WORK, StopReason.PILOT_COMPLETE, None}:
            return self._finish(BrokerOutcome.COMPLETE)
        return self._finish(BrokerOutcome.COMPLETE)

    def _classify(
        self,
        loop_result: object,
        *,
        recovered: bool,
        fresh_cycle: bool,
    ) -> BrokerCycleResult:
        del fresh_cycle
        phase = getattr(loop_result, "phase", None)
        stop_reason = getattr(loop_result, "stop_reason", None)
        dispatched = bool(getattr(loop_result, "dispatched", False))
        package_id = getattr(loop_result, "package_id", None)
        if phase is LoopPhase.FAILED_CLOSED or stop_reason is StopReason.SAFETY_BOUNDARY:
            return self._finish(
                BrokerOutcome.SAFETY_STOP,
                recovered=recovered,
                dispatched=dispatched,
                package_id=package_id,
            )
        if phase is LoopPhase.AWAITING_RESULT:
            return self._finish(
                BrokerOutcome.WAITING_RESULT,
                recovered=recovered,
                dispatched=dispatched,
                package_id=package_id,
                continuation=True,
            )
        if phase is LoopPhase.STOPPED:
            if stop_reason is StopReason.OWNER_GATE:
                prompts = self._park_owner_from_governor()
                return self._finish(
                    BrokerOutcome.WAITING_OWNER,
                    recovered=recovered,
                    dispatched=dispatched,
                    package_id=package_id,
                    owner_prompts=prompts,
                )
            if stop_reason is StopReason.HARD_BLOCKER:
                if _safe_work_exists(self._governor):
                    return self._checkpoint_continue(
                        recovered=recovered,
                        dispatched=dispatched,
                        package_id=package_id,
                    )
                return self._finish(
                    BrokerOutcome.HARD_BLOCKED,
                    recovered=recovered,
                    dispatched=dispatched,
                    package_id=package_id,
                )
            if stop_reason is StopReason.RESOURCE_BOUNDARY:
                if _safe_work_exists(self._governor) or self._loop.state.phase in {
                    LoopPhase.AWAITING_RESULT,
                    LoopPhase.DISPATCHING,
                }:
                    self._loop.begin_fresh_invocation()
                    return self._checkpoint_continue(
                        recovered=recovered,
                        dispatched=dispatched,
                        package_id=package_id,
                    )
                return self._finish(
                    BrokerOutcome.COMPLETE,
                    recovered=recovered,
                    dispatched=dispatched,
                    package_id=package_id,
                )
            if stop_reason in {StopReason.NO_ELIGIBLE_WORK, StopReason.PILOT_COMPLETE}:
                if _safe_work_exists(self._governor):
                    return self._checkpoint_continue(
                        recovered=recovered,
                        dispatched=dispatched,
                        package_id=package_id,
                    )
                snapshot = self._governor.snapshot()
                owner_only = any(
                    node.state in {NodeState.OWNER_HELD, NodeState.MERGE_ELIGIBLE}
                    and node.owner_gate is not None
                    for node in snapshot.nodes
                ) and not _ready_count(self._governor)
                if owner_only:
                    prompts = self._park_owner_from_governor()
                    return self._finish(
                        BrokerOutcome.WAITING_OWNER,
                        recovered=recovered,
                        dispatched=dispatched,
                        package_id=package_id,
                        owner_prompts=prompts,
                    )
                return self._finish(
                    BrokerOutcome.COMPLETE,
                    recovered=recovered,
                    dispatched=dispatched,
                    package_id=package_id,
                )
        if _safe_work_exists(self._governor) or phase is LoopPhase.IDLE:
            if phase is LoopPhase.IDLE and not _safe_work_exists(self._governor):
                snapshot = self._governor.snapshot()
                owner_only = any(
                    node.state in {NodeState.OWNER_HELD, NodeState.MERGE_ELIGIBLE}
                    and node.owner_gate is not None
                    for node in snapshot.nodes
                )
                if owner_only:
                    prompts = self._park_owner_from_governor()
                    return self._finish(
                        BrokerOutcome.WAITING_OWNER,
                        recovered=recovered,
                        dispatched=dispatched,
                        package_id=package_id,
                        owner_prompts=prompts,
                    )
                return self._finish(
                    BrokerOutcome.COMPLETE,
                    recovered=recovered,
                    dispatched=dispatched,
                    package_id=package_id,
                )
            return self._checkpoint_continue(
                recovered=recovered,
                dispatched=dispatched,
                package_id=package_id,
            )
        return self._finish(
            BrokerOutcome.COMPLETE,
            recovered=recovered,
            dispatched=dispatched,
            package_id=package_id,
        )

    def _park_owner_from_governor(self) -> int:
        snapshot = self._governor.snapshot()
        held = next(
            (
                node
                for node in snapshot.nodes
                if node.state in {NodeState.OWNER_HELD, NodeState.MERGE_ELIGIBLE}
                and node.owner_gate is not None
            ),
            None,
        )
        gate_id = held.package_id if held is not None else BATCH_B_OWNER_REQUEST_ID
        authority = (
            held.owner_gate.value
            if held is not None and held.owner_gate is not None
            else BATCH_B_AUTHORITY
        )
        _record, prompts = self.observe_owner_gate(
            gate_id=gate_id,
            current_main=snapshot.current_main,
            candidate_head=snapshot.current_main,
            candidate_tree=snapshot.current_tree,
            requested_authority_class=authority,
        )
        return prompts

    def _checkpoint_continue(
        self,
        *,
        recovered: bool,
        dispatched: bool,
        package_id: str | None,
    ) -> BrokerCycleResult:
        cycle_id = self._state.current_cycle_id or _cycle_id(self._state.dag_generation)
        digest = hash_payload(
            {
                "cycle_id": cycle_id,
                "outcome": BrokerOutcome.CONTINUE.value,
                "main_sha": self._state.main_sha,
                "main_tree": self._state.main_tree,
                "dag_generation": self._state.dag_generation,
                "package_id": package_id,
                "dispatch_id": self._loop.state.active_dispatch_id,
                "sequence": self._loop.state.sequence,
            }
        )
        if digest in self._state.seen_checkpoint_digests:
            self._save(last_checkpoint_replay="IGNORED")
            return self._result(
                BrokerOutcome.CONTINUE,
                checkpoint_replay="IGNORED",
                recovered=recovered,
                dispatched=False,
                package_id=package_id,
            )
        successor = _cycle_id(self._state.dag_generation + 1)
        result_digest = digest
        self._save(
            checkpoint_digest=digest,
            seen_checkpoint_digests=(*self._state.seen_checkpoint_digests, digest),
            seen_cycle_ids=(*self._state.seen_cycle_ids, cycle_id)
            if cycle_id not in self._state.seen_cycle_ids
            else self._state.seen_cycle_ids,
            seen_result_digests=(*self._state.seen_result_digests, result_digest),
            successor_cycle_id=successor,
            successor_started=False,
            outcome=BrokerOutcome.CONTINUE,
            active_dispatch_id=self._loop.state.active_dispatch_id,
            active_lease_id=self._loop.state.active_lease_id,
            last_result_digest=result_digest,
            last_loop_phase=self._loop.state.phase.value,
            last_stop_reason=(
                self._loop.state.stop_reason.value if self._loop.state.stop_reason else None
            ),
            safe_work_remaining=_safe_work_exists(self._governor),
            last_checkpoint_replay="NONE",
        )
        self._maybe_crash("CHECKPOINT_WRITTEN")
        return self._result(
            BrokerOutcome.CONTINUE,
            recovered=recovered,
            dispatched=dispatched,
            package_id=package_id,
            continuation=True,
        )

    def _finish(
        self,
        outcome: BrokerOutcome,
        *,
        recovered: bool = False,
        dispatched: bool = False,
        package_id: str | None = None,
        owner_prompts: int = 0,
        continuation: bool = False,
    ) -> BrokerCycleResult:
        cycle_id = self._state.current_cycle_id
        digest = hash_payload(
            {
                "cycle_id": cycle_id,
                "outcome": outcome.value,
                "main_sha": self._state.main_sha,
                "main_tree": self._state.main_tree,
                "dag_generation": self._state.dag_generation,
                "package_id": package_id,
                "dispatch_id": self._loop.state.active_dispatch_id,
                "sequence": self._loop.state.sequence,
            }
        )
        seen_cycles = self._state.seen_cycle_ids
        if cycle_id is not None and cycle_id not in seen_cycles:
            seen_cycles = (*seen_cycles, cycle_id)
        self._save(
            outcome=outcome,
            checkpoint_digest=digest,
            seen_checkpoint_digests=(*self._state.seen_checkpoint_digests, digest)
            if digest not in self._state.seen_checkpoint_digests
            else self._state.seen_checkpoint_digests,
            seen_cycle_ids=seen_cycles,
            seen_result_digests=(*self._state.seen_result_digests, digest)
            if digest not in self._state.seen_result_digests
            else self._state.seen_result_digests,
            successor_cycle_id=None,
            successor_started=False,
            active_dispatch_id=self._loop.state.active_dispatch_id,
            active_lease_id=self._loop.state.active_lease_id,
            last_result_digest=digest,
            last_loop_phase=self._loop.state.phase.value,
            last_stop_reason=(
                self._loop.state.stop_reason.value if self._loop.state.stop_reason else None
            ),
            safe_work_remaining=_safe_work_exists(self._governor),
            last_checkpoint_replay="NONE",
        )
        return self._result(
            outcome,
            recovered=recovered,
            dispatched=dispatched,
            package_id=package_id,
            owner_prompts=owner_prompts,
            continuation=continuation
            or outcome in {BrokerOutcome.CONTINUE, BrokerOutcome.WAITING_RESULT},
        )

    def _result(
        self,
        outcome: BrokerOutcome,
        *,
        checkpoint_replay: Literal["NONE", "IGNORED"] = "NONE",
        recovered: bool = False,
        dispatched: bool = False,
        package_id: str | None = None,
        owner_prompts: int = 0,
        continuation: bool = False,
        duplicate_successor: bool = False,
    ) -> BrokerCycleResult:
        return BrokerCycleResult(
            outcome=outcome,
            cycle_id=self._state.current_cycle_id,
            successor_cycle_id=self._state.successor_cycle_id,
            checkpoint_digest=self._state.checkpoint_digest,
            checkpoint_replay=checkpoint_replay,
            owner_prompts=owner_prompts,
            owner_notification_count=self._state.owner_notification_count,
            dispatched=dispatched,
            recovered=recovered,
            package_id=package_id,
            worker_exited=True,
            primary_dag_continuation=continuation or outcome is BrokerOutcome.CONTINUE,
            human_scheduler_events=owner_prompts,
            duplicate_dispatch=False,
            duplicate_successor=duplicate_successor,
        )
