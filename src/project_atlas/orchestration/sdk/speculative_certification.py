"""AS-ORCH-SPECULATIVE-CERTIFICATION-001 — durable candidate-seal + exact-pin barrier.

Encodes the successful D-121/D-122 protocol as a first-class orchestration capability:

* candidate seal binds HEAD/TREE/BASE_MAIN/generation (+ required lanes)
* parallel lane receipts must bind sealed pins + generation
* tip drift cancels certification (no silent repair)
* exact-pin evidence promotion is explicit and fail-closed
* merge authorization is never granted by this module
* durable JSON uses atomic replace under a single-writer lock

Evidence only. Not merge authority.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.sdk.models import SdkRuntimeError
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

SPECULATIVE_PACKAGE_ID: Final[Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"]] = (
    "AS-ORCH-SPECULATIVE-CERTIFICATION-001"
)
SEAL_DIR_NAME: Final[str] = "speculative-cert"
SEAL_FILE_NAME: Final[str] = "candidate-seal.json"
BARRIER_FILE_NAME: Final[str] = "certification-barrier.json"
PROMOTED_FILE_NAME: Final[str] = "exact-pin-evidence-promoted.json"
LOCK_FILE_NAME: Final[str] = ".speculative-cert.lock"

# Default lane set (G107-style protocol). Packages may override at seal time.
REQUIRED_LANES: Final[tuple[str, ...]] = (
    "CI",
    "IV",
    "ADV",
    "CLOUD_RUNTIME_AUDIT",
    "D116_D119_D121",
    "PRIOR_P1_REGRESSION",
    "AUTHENTIC_CLOUD_SMOKE_V2",
    "FINAL_LINEAGE_AUDIT",
)

# Package certification barrier for dogfooding this capability on PR430.
PACKAGE_CERT_LANES: Final[tuple[str, ...]] = (
    "EXACT_HEAD_CI",
    "INDEPENDENT_IV",
    "ADV_SECURITY_AND_STATE_MACHINE",
    "DURABILITY_CRASH_RECOVERY",
    "CONCURRENCY_RACE_ATTACK",
    "PRIOR_ORCHESTRATION_REGRESSION",
    "DOGFOOD_ORACLE_PARITY",
    "FINAL_LINEAGE_PIN_AUDIT",
)

_FULL_SHA_LEN: Final[int] = 40
_MERGE_DENIED: Final[Literal["NOT_GRANTED"]] = "NOT_GRANTED"

# Process-local RLock plus ProjectIdentityLock for cross-process single-writer updates.
class _DurableGuard:
    def __init__(self) -> None:
        self.thread_lock = threading.RLock()
        self.depth = 0
        self.file_lock: ProjectIdentityLock | None = None


_DURABLE_GUARDS: dict[str, _DurableGuard] = {}
_DURABLE_GUARDS_GUARD = threading.Lock()


def _durable_guard(root: Path) -> _DurableGuard:
    key = str(root.resolve())
    with _DURABLE_GUARDS_GUARD:
        guard = _DURABLE_GUARDS.get(key)
        if guard is None:
            guard = _DurableGuard()
            _DURABLE_GUARDS[key] = guard
        return guard


@contextmanager
def _root_lock(root: Path) -> Iterator[None]:
    """Reentrant in-process lock; outermost entry also acquires LOCK_FILE_NAME."""
    guard = _durable_guard(root)
    with guard.thread_lock:
        acquired_file = False
        if guard.depth == 0:
            file_lock = ProjectIdentityLock(
                speculative_cert_dir(root) / LOCK_FILE_NAME,
                wait_seconds=2.0,
                stale_seconds=30.0,
            )
            try:
                file_lock.acquire()
            except IdentityLockError as exc:
                raise SdkRuntimeError(
                    "speculative certification lock is held",
                    code="SPECULATIVE_CERT_CONCURRENT",
                ) from exc
            guard.file_lock = file_lock
            acquired_file = True
        guard.depth += 1
        try:
            yield
        finally:
            guard.depth -= 1
            if acquired_file and guard.file_lock is not None:
                guard.file_lock.release()
                guard.file_lock = None


def _require_full_sha(value: str, *, field: str) -> str:
    text = value.strip()
    # Exact lowercase only — uppercase/mixed SHAs fail closed (no silent normalize).
    if len(text) != _FULL_SHA_LEN or any(c not in "0123456789abcdef" for c in text):
        raise SdkRuntimeError(
            f"{field} must be a full 40-char lowercase hex SHA",
            code="SPECULATIVE_CERT_PIN_INVALID",
        )
    return text


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json_atomic(target: Path, payload: dict[str, object]) -> None:
    """Write JSON via temp + flush + os.replace (no torn authoritative files)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            with suppress(OSError):
                tmp.unlink()


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SdkRuntimeError(
            f"unable to read durable state: {path.name}",
            code="SPECULATIVE_CERT_IO_ERROR",
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SdkRuntimeError(
            f"torn or corrupt durable JSON: {path.name}",
            code="SPECULATIVE_CERT_TORN_WRITE",
        ) from exc
    if not isinstance(data, dict):
        raise SdkRuntimeError(
            f"durable JSON must be an object: {path.name}",
            code="SPECULATIVE_CERT_TORN_WRITE",
        )
    # Strip any injected merge grant — module never grants merge.
    data["merge_authorization"] = _MERGE_DENIED
    return data


class CertificationState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    CANDIDATE_SEALED = "CANDIDATE_SEALED"
    BARRIER_OPEN = "BARRIER_OPEN"
    CERTIFIED = "CERTIFIED"
    EVIDENCE_PROMOTED = "EVIDENCE_PROMOTED"
    CANCELLED_TIP_DRIFT = "CANCELLED_TIP_DRIFT"
    BARRIER_FAILED = "BARRIER_FAILED"


class LaneResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


_TERMINAL_NO_MUTATE: Final[frozenset[CertificationState]] = frozenset(
    {
        CertificationState.CERTIFIED,
        CertificationState.EVIDENCE_PROMOTED,
        CertificationState.CANCELLED_TIP_DRIFT,
        CertificationState.BARRIER_FAILED,
    }
)


class CandidateSeal(BaseModel):
    """Frozen candidate object. Observed thereafter; not improved in-generation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"] = SPECULATIVE_PACKAGE_ID
    generation: int = Field(ge=1, le=1_000_000)
    head: str
    tree: str
    base_main: str
    required_lanes: tuple[str, ...] = REQUIRED_LANES
    sealed_at_utc: str
    certification_frozen: Literal[False] = False
    merge_authorization: Literal["NOT_GRANTED"] = _MERGE_DENIED

    @field_validator("head", "tree", "base_main")
    @classmethod
    def _sha(cls, value: str) -> str:
        return _require_full_sha(value, field="pin")

    @field_validator("required_lanes")
    @classmethod
    def _lanes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise SdkRuntimeError(
                "required_lanes must be non-empty",
                code="SPECULATIVE_CERT_LANE_MISSING",
            )
        if len(set(value)) != len(value):
            raise SdkRuntimeError(
                "required_lanes must be unique",
                code="SPECULATIVE_CERT_LANE_MISSING",
            )
        return value


class LaneReceipt(BaseModel):
    """One parallel certification lane bound to the sealed pins + generation."""

    model_config = ConfigDict(extra="forbid")

    lane: str
    result: LaneResult
    head: str
    tree: str
    generation: int = Field(ge=1, le=1_000_000)
    package_id: Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"] = SPECULATIVE_PACKAGE_ID
    new_p0: int = Field(default=0, ge=0)
    new_p1: int = Field(default=0, ge=0)
    previous_p1_reopened: int = Field(default=0, ge=0)

    @field_validator("head", "tree")
    @classmethod
    def _sha(cls, value: str) -> str:
        return _require_full_sha(value, field="lane_pin")


class CertificationBarrier(BaseModel):
    """Aggregate exact-pin barrier over required lanes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"] = SPECULATIVE_PACKAGE_ID
    generation: int = Field(ge=1, le=1_000_000)
    sealed_head: str
    sealed_tree: str
    sealed_base_main: str
    required_lanes: tuple[str, ...] = REQUIRED_LANES
    state: CertificationState
    lanes: dict[str, LaneReceipt]
    new_p0: int = Field(default=0, ge=0)
    new_p1: int = Field(default=0, ge=0)
    previous_p1_reopened: int = Field(default=0, ge=0)
    exact_pin_evidence_promoted: bool = False
    certification_frozen: bool = False
    merge_authorization: Literal["NOT_GRANTED"] = _MERGE_DENIED
    updated_at_utc: str

    @model_validator(mode="after")
    def _lane_keys(self) -> CertificationBarrier:
        missing = [name for name in self.required_lanes if name not in self.lanes]
        if missing:
            raise SdkRuntimeError(
                f"barrier missing required lanes: {missing}",
                code="SPECULATIVE_CERT_LANE_MISSING",
            )
        extras = [name for name in self.lanes if name not in self.required_lanes]
        if extras:
            raise SdkRuntimeError(
                f"barrier has unknown lanes: {extras}",
                code="SPECULATIVE_CERT_LANE_UNKNOWN",
            )
        return self


def speculative_cert_dir(root: Path) -> Path:
    return root / ".atlas" / "orchestration" / "sdk-runtime" / SEAL_DIR_NAME


def _pending_lanes(
    *,
    lanes: Sequence[str],
    head: str,
    tree: str,
    generation: int,
) -> dict[str, LaneReceipt]:
    return {
        name: LaneReceipt(
            lane=name,
            result=LaneResult.PENDING,
            head=head,
            tree=tree,
            generation=generation,
        )
        for name in lanes
    }


def _pending_barrier_from_seal(
    seal: CandidateSeal, *, updated_at_utc: str
) -> CertificationBarrier:
    return CertificationBarrier(
        generation=seal.generation,
        sealed_head=seal.head,
        sealed_tree=seal.tree,
        sealed_base_main=seal.base_main,
        required_lanes=seal.required_lanes,
        state=CertificationState.CANDIDATE_SEALED,
        lanes=_pending_lanes(
            lanes=seal.required_lanes,
            head=seal.head,
            tree=seal.tree,
            generation=seal.generation,
        ),
        updated_at_utc=updated_at_utc,
    )


def _barrier_binds_seal(barrier: CertificationBarrier, seal: CandidateSeal) -> bool:
    return (
        barrier.generation == seal.generation
        and barrier.sealed_head == seal.head
        and barrier.sealed_tree == seal.tree
        and barrier.sealed_base_main == seal.base_main
        and barrier.required_lanes == seal.required_lanes
    )


def _persist_seal(root: Path, seal: CandidateSeal) -> None:
    _write_json_atomic(
        speculative_cert_dir(root) / SEAL_FILE_NAME,
        seal.model_dump(mode="json"),
    )


def _persist_barrier(root: Path, barrier: CertificationBarrier) -> None:
    payload = barrier.model_dump(mode="json")
    payload["merge_authorization"] = _MERGE_DENIED
    _write_json_atomic(speculative_cert_dir(root) / BARRIER_FILE_NAME, payload)


def _persist_promoted(root: Path, seal: CandidateSeal, promoted_at_utc: str) -> None:
    _write_json_atomic(
        speculative_cert_dir(root) / PROMOTED_FILE_NAME,
        {
            "package_id": SPECULATIVE_PACKAGE_ID,
            "generation": seal.generation,
            "head": seal.head,
            "tree": seal.tree,
            "base_main": seal.base_main,
            "exact_pin_evidence_promoted": True,
            "certification_frozen": True,
            "merge_authorization": _MERGE_DENIED,
            "promoted_at_utc": promoted_at_utc,
        },
    )


def seal_candidate(
    root: Path,
    *,
    generation: int,
    head: str,
    tree: str,
    base_main: str,
    required_lanes: Sequence[str] | None = None,
) -> CandidateSeal:
    """Seal a candidate tip. Does not grant merge authority."""
    with _root_lock(root):
        lanes = tuple(required_lanes) if required_lanes is not None else REQUIRED_LANES
        seal = CandidateSeal(
            generation=generation,
            head=_require_full_sha(head, field="head"),
            tree=_require_full_sha(tree, field="tree"),
            base_main=_require_full_sha(base_main, field="base_main"),
            required_lanes=lanes,
            sealed_at_utc=_utc_now(),
        )
        path = speculative_cert_dir(root)
        path.mkdir(parents=True, exist_ok=True)
        # Drop the prior barrier first so a crash cannot pair a new seal with a stale barrier.
        barrier_path = path / BARRIER_FILE_NAME
        if barrier_path.is_file():
            barrier_path.unlink()
        _persist_seal(root, seal)
        _persist_barrier(
            root, _pending_barrier_from_seal(seal, updated_at_utc=seal.sealed_at_utc)
        )
        # Drop any prior promotion artifact from an older generation.
        promoted = path / PROMOTED_FILE_NAME
        if promoted.exists():
            promoted.unlink()
        return seal


def load_candidate_seal(root: Path) -> CandidateSeal:
    path = speculative_cert_dir(root) / SEAL_FILE_NAME
    if not path.is_file():
        raise SdkRuntimeError("candidate seal missing", code="SPECULATIVE_CERT_SEAL_MISSING")
    return CandidateSeal.model_validate(_read_json_object(path))


def load_barrier(root: Path) -> CertificationBarrier:
    """Load barrier; rebuild from seal when missing or generation/pin-desynced."""
    with _root_lock(root):
        seal_path = speculative_cert_dir(root) / SEAL_FILE_NAME
        barrier_path = speculative_cert_dir(root) / BARRIER_FILE_NAME
        if not seal_path.is_file() and not barrier_path.is_file():
            raise SdkRuntimeError(
                "barrier missing",
                code="SPECULATIVE_CERT_BARRIER_MISSING",
            )
        if barrier_path.is_file() and not seal_path.is_file():
            raise SdkRuntimeError(
                "barrier present without seal",
                code="SPECULATIVE_CERT_SEAL_MISSING",
            )
        seal = CandidateSeal.model_validate(_read_json_object(seal_path))
        if barrier_path.is_file():
            barrier = CertificationBarrier.model_validate(_read_json_object(barrier_path))
            if _barrier_binds_seal(barrier, seal):
                return barrier
        barrier = _pending_barrier_from_seal(seal, updated_at_utc=_utc_now())
        _persist_barrier(root, barrier)
        return barrier


def observe_live_pins(
    *,
    live_head: str,
    live_tree: str,
    live_main: str,
    seal: CandidateSeal,
) -> tuple[bool, bool, bool]:
    """Return (head_match, tree_match, target_moved)."""
    head_match = _require_full_sha(live_head, field="live_head") == seal.head
    tree_match = _require_full_sha(live_tree, field="live_tree") == seal.tree
    target_moved = _require_full_sha(live_main, field="live_main") != seal.base_main
    return head_match, tree_match, target_moved


def cancel_for_tip_drift(root: Path, *, live_head: str, live_tree: str) -> CertificationBarrier:
    """Cancel certification when the sealed tip moved. No repair in-generation."""
    with _root_lock(root):
        _ = (
            _require_full_sha(live_head, field="live_head"),
            _require_full_sha(live_tree, field="live_tree"),
        )
        barrier = load_barrier(root)
        if barrier.state == CertificationState.EVIDENCE_PROMOTED:
            # Frozen cert tip drift cancels promotion flags.
            pass
        updated = barrier.model_copy(
            update={
                "state": CertificationState.CANCELLED_TIP_DRIFT,
                "certification_frozen": False,
                "exact_pin_evidence_promoted": False,
                "merge_authorization": _MERGE_DENIED,
                "updated_at_utc": _utc_now(),
            }
        )
        _persist_barrier(root, updated)
        promoted = speculative_cert_dir(root) / PROMOTED_FILE_NAME
        if promoted.exists():
            promoted.unlink()
        return updated


def _accept_lane_transition(current: LaneReceipt, incoming: LaneReceipt) -> LaneReceipt | None:
    """Return receipt to store, or None if idempotent no-op. Raises on stale/illegal."""
    if current.result == LaneResult.PENDING:
        if incoming.result == LaneResult.PENDING:
            return None
        return incoming
    if current.result == incoming.result and current.model_dump() == incoming.model_dump():
        return None  # exact duplicate
    # Same terminal result with identical severity counters — idempotent.
    if (
        current.result == incoming.result
        and current.new_p0 == incoming.new_p0
        and current.new_p1 == incoming.new_p1
        and current.previous_p1_reopened == incoming.previous_p1_reopened
    ):
        return None
    raise SdkRuntimeError(
        f"stale or conflicting lane receipt for {incoming.lane}: "
        f"{current.result} -> {incoming.result}",
        code="SPECULATIVE_CERT_STALE_RECEIPT",
    )


def record_lane_result(root: Path, receipt: LaneReceipt) -> CertificationBarrier:
    """Record a lane result. Rejects pin/generation mismatch and stale transitions."""
    with _root_lock(root):
        seal = load_candidate_seal(root)
        barrier = load_barrier(root)
        if barrier.state in _TERMINAL_NO_MUTATE:
            raise SdkRuntimeError(
                f"lane mutation refused in terminal state {barrier.state}",
                code="SPECULATIVE_CERT_TERMINAL",
            )
        if receipt.package_id != SPECULATIVE_PACKAGE_ID:
            raise SdkRuntimeError(
                "foreign package receipt rejected",
                code="SPECULATIVE_CERT_FOREIGN_PACKAGE",
            )
        if receipt.generation != seal.generation or receipt.generation != barrier.generation:
            raise SdkRuntimeError(
                "cross-generation receipt rejected",
                code="SPECULATIVE_CERT_CROSS_GENERATION",
            )
        if receipt.lane not in barrier.required_lanes:
            raise SdkRuntimeError(
                f"unknown lane {receipt.lane}",
                code="SPECULATIVE_CERT_LANE_UNKNOWN",
            )
        if receipt.head != seal.head or receipt.tree != seal.tree:
            raise SdkRuntimeError(
                "lane receipt pin does not bind sealed candidate",
                code="SPECULATIVE_CERT_PIN_MISMATCH",
            )
        if receipt.result == LaneResult.PENDING:
            raise SdkRuntimeError(
                "cannot record PENDING as a completion",
                code="SPECULATIVE_CERT_STALE_RECEIPT",
            )
        current = barrier.lanes[receipt.lane]
        accepted = _accept_lane_transition(current, receipt)
        if accepted is None:
            return barrier
        lanes = dict(barrier.lanes)
        lanes[receipt.lane] = accepted
        new_p0 = sum(item.new_p0 for item in lanes.values())
        new_p1 = sum(item.new_p1 for item in lanes.values())
        prev = sum(item.previous_p1_reopened for item in lanes.values())
        updated = barrier.model_copy(
            update={
                "lanes": lanes,
                "new_p0": new_p0,
                "new_p1": new_p1,
                "previous_p1_reopened": prev,
                "state": CertificationState.BARRIER_OPEN,
                "merge_authorization": _MERGE_DENIED,
                "updated_at_utc": _utc_now(),
            }
        )
        _persist_barrier(root, updated)
        return updated


def evaluate_barrier(root: Path) -> CertificationBarrier:
    """Evaluate whether all required lanes PASS on exact sealed pins."""
    with _root_lock(root):
        barrier = load_barrier(root)
        if barrier.state in {
            CertificationState.CANCELLED_TIP_DRIFT,
            CertificationState.EVIDENCE_PROMOTED,
            CertificationState.BARRIER_FAILED,
            CertificationState.CERTIFIED,
        }:
            # Idempotent: do not resurrect FAILED/CANCELLED into CERTIFIED.
            return barrier
        pending = [
            name
            for name, receipt in barrier.lanes.items()
            if receipt.result == LaneResult.PENDING
        ]
        failed = [
            name
            for name, receipt in barrier.lanes.items()
            if receipt.result == LaneResult.FAIL
            or receipt.head != barrier.sealed_head
            or receipt.tree != barrier.sealed_tree
            or receipt.generation != barrier.generation
        ]
        if pending:
            return barrier
        if failed or barrier.new_p0 or barrier.new_p1 or barrier.previous_p1_reopened:
            updated = barrier.model_copy(
                update={
                    "state": CertificationState.BARRIER_FAILED,
                    "merge_authorization": _MERGE_DENIED,
                    "updated_at_utc": _utc_now(),
                }
            )
            _persist_barrier(root, updated)
            return updated
        updated = barrier.model_copy(
            update={
                "state": CertificationState.CERTIFIED,
                "merge_authorization": _MERGE_DENIED,
                "updated_at_utc": _utc_now(),
            }
        )
        _persist_barrier(root, updated)
        return updated


def promote_exact_pin_evidence(
    root: Path,
    *,
    live_head: str,
    live_tree: str,
    live_main: str,
) -> CertificationBarrier:
    """Promote exact-pin evidence only while tip/main remain sealed and barrier CERTIFIED."""
    with _root_lock(root):
        seal = load_candidate_seal(root)
        barrier = load_barrier(root)
        if barrier.state == CertificationState.EVIDENCE_PROMOTED:
            return barrier
        head_match, tree_match, target_moved = observe_live_pins(
            live_head=live_head,
            live_tree=live_tree,
            live_main=live_main,
            seal=seal,
        )
        if not head_match or not tree_match:
            return cancel_for_tip_drift(root, live_head=live_head, live_tree=live_tree)
        # Evaluate only after live tip matches — never persist CERTIFIED then cancel.
        barrier = evaluate_barrier(root)
        if not _barrier_binds_seal(barrier, seal):
            raise SdkRuntimeError(
                "barrier does not bind current sealed candidate",
                code="SPECULATIVE_CERT_PIN_MISMATCH",
            )
        if target_moved:
            raise SdkRuntimeError(
                "target main moved; merge authorization remains NOT_GRANTED",
                code="SPECULATIVE_CERT_TARGET_MOVED",
            )
        if barrier.state != CertificationState.CERTIFIED:
            raise SdkRuntimeError(
                "barrier not CERTIFIED; refuse exact-pin promotion",
                code="SPECULATIVE_CERT_NOT_CERTIFIED",
            )
        if (
            barrier.new_p0
            or barrier.new_p1
            or barrier.previous_p1_reopened
            or any(r.result != LaneResult.PASS for r in barrier.lanes.values())
        ):
            raise SdkRuntimeError(
                "promotion predicates failed",
                code="SPECULATIVE_CERT_NOT_CERTIFIED",
            )
        now = _utc_now()
        promoted = barrier.model_copy(
            update={
                "state": CertificationState.EVIDENCE_PROMOTED,
                "exact_pin_evidence_promoted": True,
                "certification_frozen": True,
                "merge_authorization": _MERGE_DENIED,
                "updated_at_utc": now,
            }
        )
        _persist_barrier(root, promoted)
        _persist_promoted(root, seal, now)
        return promoted
