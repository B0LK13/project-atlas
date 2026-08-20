"""AS-ORCH-CONTINUATION-BROKER-001 — lifecycle continuation, not authority.

Reuses AS-ORCH-001D (single-hop dispatch) and AS-ORCH-001E (loop tick).
Does not create a second governor, DAG, dispatcher, or lease authority.

CONTINUATION_BACKEND = CURSOR_STOP_HOOK_FOLLOWUP
Durable consume-once cycle store is the invocation contract.
The 001C Cursor bridge slot is never read or written here
(PR400 leftover must remain unconsumed).

RESULT != AUTHORITY / FOLLOWUP != DISPATCH / YIELD != OWNER_REQUIRED
WORKER_TERMINAL != DAG_TERMINAL / REQUESTED_TRANSITION != AUTHORIZATION
"""

from __future__ import annotations

import json
import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.models import CANONICAL_REPOSITORY_IDENTITY
from project_atlas.orchestration.autonomy.trust import require_full_pin
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

PACKAGE_ID: Final[Literal["AS-ORCH-CONTINUATION-BROKER-001"]] = (
    "AS-ORCH-CONTINUATION-BROKER-001"
)
BACKEND: Final[Literal["CURSOR_STOP_HOOK_FOLLOWUP"]] = "CURSOR_STOP_HOOK_FOLLOWUP"
STATE_DIR_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "continuation-broker"
CURRENT_NAME: Final[str] = "current.json"
LOCK_NAME: Final[str] = ".broker.lock"
BROKER_MARKER: Final[str] = "[ATLAS_CONTINUATION_BROKER]"
PLACEHOLDER_DIGEST: Final[str] = "0" * 64
_CYCLE_RE = re.compile(r"^[A-Z][A-Z0-9._-]{0,63}$")
_FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class BrokerError(ValueError):
    """Fail-closed broker error. Not an authority grant."""

    code = "BROKER_FAILED_CLOSED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class SuccessorKind(StrEnum):
    CHECKPOINT_CONTINUE = "CHECKPOINT_CONTINUE"
    RESOURCE_YIELD = "RESOURCE_YIELD"
    WORKER_TERMINAL_DAG_CONTINUES = "WORKER_TERMINAL_DAG_CONTINUES"


class BrokerPhase(StrEnum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    FOLLOWUP_EMITTED = "FOLLOWUP_EMITTED"
    CONSUMED = "CONSUMED"
    PARKED_OWNER = "PARKED_OWNER"


class BrokerState(BaseModel):
    """Durable continuation identity. Never authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-CONTINUATION-BROKER-001"] = PACKAGE_ID
    backend: Literal["CURSOR_STOP_HOOK_FOLLOWUP"] = BACKEND
    repository_identity: str = Field(min_length=1, max_length=256)
    trusted_main: str = Field(min_length=40, max_length=40)
    trusted_tree: str = Field(min_length=40, max_length=40)
    dag_generation: int = Field(ge=0, le=1_000_000)
    cycle_id: str | None = None
    kind: SuccessorKind | None = None
    phase: BrokerPhase
    followup_emitted: bool = False
    consumed: bool = False
    owner_gate_fingerprint: str | None = None
    owner_request_id: str | None = None
    owner_request_already_emitted: bool = False
    primary_governor: Literal[True] = True
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    authority_granted: Literal[False] = False
    record_digest: str = Field(min_length=64, max_length=64)

    @field_validator("trusted_main", "trusted_tree")
    @classmethod
    def _pin(cls, value: str) -> str:
        return require_full_pin(value, "broker pin")

    @field_validator("cycle_id")
    @classmethod
    def _cycle(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _CYCLE_RE.fullmatch(value):
            raise ValueError("cycle_id must be a safe identifier")
        return value

    @field_validator("owner_gate_fingerprint", "owner_request_id")
    @classmethod
    def _token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _FINGERPRINT_RE.fullmatch(value):
            raise ValueError("owner token must be a safe identifier")
        return value

    @model_validator(mode="after")
    def _no_authority(self) -> BrokerState:
        if self.merge_authorized or self.execution_authorized or self.authority_granted:
            raise ValueError("broker state cannot carry authority")
        if self.repository_identity.casefold() != CANONICAL_REPOSITORY_IDENTITY:
            raise ValueError("cross-project broker reuse is forbidden")
        if self.consumed and self.phase not in {BrokerPhase.CONSUMED, BrokerPhase.IDLE}:
            raise ValueError("consumed successor must be CONSUMED or IDLE")
        return self

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("record_digest")
        return payload


class EnqueueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    deduped: bool = False
    phase: BrokerPhase
    cycle_id: str | None = None
    kind: SuccessorKind | None = None
    owner_prompt_emitted: bool = False
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def seal_broker_state(state: BrokerState) -> BrokerState:
    return state.model_copy(update={"record_digest": hash_payload(state.unsigned_payload())})


def verify_broker_state(state: BrokerState) -> BrokerState:
    expected = hash_payload(state.unsigned_payload())
    if state.record_digest != expected:
        raise BrokerError("broker state digest mismatch", code="STATE_CORRUPT")
    return state


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_broker_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise BrokerError("repository root is not a directory", code="PATH_UNSAFE")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise BrokerError("refusing filesystem root or home as broker root", code="PATH_UNSAFE")
    return resolved


def _store_path(root: Path, relative: str) -> Path:
    if ".." in Path(relative).parts or Path(relative).is_absolute():
        raise BrokerError("broker store path is unsafe", code="PATH_UNSAFE")
    target = (root / relative).resolve()
    if not _inside(root, target):
        raise BrokerError("broker store path escapes root", code="PATH_UNSAFE")
    return target


def broker_store_dir(root: Path) -> Path:
    return resolve_broker_root(root) / STATE_DIR_RELATIVE


def _write_json_atomic(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded + "\n", encoding="utf-8")
    os.replace(tmp, target)


def persist_broker_state(store: Path, state: BrokerState) -> BrokerState:
    sealed = verify_broker_state(seal_broker_state(state))
    root = store.resolve()
    lock_path = _store_path(root, LOCK_NAME)
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            _write_json_atomic(
                _store_path(root, CURRENT_NAME),
                sealed.model_dump(mode="json"),
            )
    except IdentityLockError as exc:
        raise BrokerError("broker lock is held", code="CONCURRENT_BROKER") from exc
    return sealed


def load_broker_state(store: Path) -> BrokerState | None:
    path = _store_path(store.resolve(), CURRENT_NAME)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise BrokerError("broker state is schema-invalid", code="STATE_CORRUPT")
        return verify_broker_state(BrokerState.model_validate(payload))
    except BrokerError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise BrokerError("broker state is unreadable", code="STATE_CORRUPT") from exc


def initial_broker_state(*, trusted_main: str, trusted_tree: str) -> BrokerState:
    return seal_broker_state(
        BrokerState(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=trusted_main,
            trusted_tree=trusted_tree,
            dag_generation=0,
            phase=BrokerPhase.IDLE,
            record_digest=PLACEHOLDER_DIGEST,
        )
    )


def session_exit_does_not_end_dag(*, worker_terminal: bool, dag_terminal: bool) -> bool:
    """Worker/session terminal is not DAG terminal."""
    del worker_terminal
    return not dag_terminal


def _require_identity(repository_identity: str) -> str:
    identity = repository_identity.strip()
    if identity.casefold() != CANONICAL_REPOSITORY_IDENTITY:
        raise BrokerError("foreign project broker reuse is forbidden", code="FOREIGN_PROJECT")
    return CANONICAL_REPOSITORY_IDENTITY


def enqueue_successor(
    root: Path,
    *,
    cycle_id: str,
    kind: SuccessorKind,
    trusted_main: str,
    trusted_tree: str,
    repository_identity: str = CANONICAL_REPOSITORY_IDENTITY,
    dag_generation: int = 0,
    dag_terminal: bool = False,
    worker_terminal: bool = False,
    owner_gate_fingerprint: str | None = None,
    owner_request_id: str | None = None,
    primary_governor: bool = True,
) -> EnqueueResult:
    """Queue exactly one successor for a governor cycle. Consume-once."""
    if not primary_governor:
        raise BrokerError("second governor is forbidden", code="SECOND_GOVERNOR")
    if not _CYCLE_RE.fullmatch(cycle_id):
        raise BrokerError("cycle_id is unsafe", code="UNSAFE_CYCLE_ID")
    _require_identity(repository_identity)
    require_full_pin(trusted_main, "broker main")
    require_full_pin(trusted_tree, "broker tree")
    if kind == SuccessorKind.WORKER_TERMINAL_DAG_CONTINUES and not session_exit_does_not_end_dag(
        worker_terminal=worker_terminal, dag_terminal=dag_terminal
    ):
        raise BrokerError("DAG is terminal; no successor", code="DAG_TERMINAL")
    if dag_terminal:
        raise BrokerError("DAG is terminal; no successor", code="DAG_TERMINAL")
    store = broker_store_dir(root)
    store.mkdir(parents=True, exist_ok=True)
    existing = load_broker_state(store)
    if existing is None:
        existing = persist_broker_state(
            store, initial_broker_state(trusted_main=trusted_main, trusted_tree=trusted_tree)
        )
    if (
        existing.trusted_main != trusted_main
        or existing.trusted_tree != trusted_tree
    ) and existing.phase in {BrokerPhase.QUEUED, BrokerPhase.FOLLOWUP_EMITTED}:
        raise BrokerError("stale checkpoint pin does not match", code="STALE_CHECKPOINT")
    if (
        owner_gate_fingerprint
        and existing.owner_gate_fingerprint == owner_gate_fingerprint
        and existing.owner_request_already_emitted
    ):
        return EnqueueResult(
            accepted=False,
            deduped=True,
            phase=existing.phase,
            cycle_id=existing.cycle_id,
            kind=existing.kind,
            owner_prompt_emitted=False,
        )
    if existing.phase in {BrokerPhase.QUEUED, BrokerPhase.FOLLOWUP_EMITTED}:
        if existing.cycle_id == cycle_id and existing.kind == kind:
            return EnqueueResult(
                accepted=True,
                deduped=True,
                phase=existing.phase,
                cycle_id=existing.cycle_id,
                kind=existing.kind,
            )
        raise BrokerError("duplicate successor is forbidden", code="DUPLICATE_SUCCESSOR")
    if existing.consumed and existing.cycle_id == cycle_id:
        raise BrokerError("cycle already consumed", code="CYCLE_REPLAY")
    parked = owner_gate_fingerprint is not None
    updated = persist_broker_state(
        store,
        existing.model_copy(
            update={
                "trusted_main": trusted_main,
                "trusted_tree": trusted_tree,
                "dag_generation": dag_generation,
                "cycle_id": cycle_id,
                "kind": kind,
                "phase": BrokerPhase.PARKED_OWNER if parked else BrokerPhase.QUEUED,
                "followup_emitted": False,
                "consumed": False,
                "owner_gate_fingerprint": owner_gate_fingerprint,
                "owner_request_id": owner_request_id,
                "owner_request_already_emitted": bool(owner_gate_fingerprint),
            }
        ),
    )
    return EnqueueResult(
        accepted=True,
        phase=updated.phase,
        cycle_id=updated.cycle_id,
        kind=updated.kind,
        owner_prompt_emitted=bool(owner_gate_fingerprint)
        and not existing.owner_request_already_emitted,
    )


def consume_successor(root: Path, cycle_id: str) -> BrokerState:
    """Consume a queued/emitted successor exactly once."""
    if not _CYCLE_RE.fullmatch(cycle_id):
        raise BrokerError("cycle_id is unsafe", code="UNSAFE_CYCLE_ID")
    store = broker_store_dir(root)
    existing = load_broker_state(store)
    if existing is None or existing.cycle_id != cycle_id:
        raise BrokerError("successor cycle is not queued", code="CYCLE_MISSING")
    if existing.consumed or existing.phase == BrokerPhase.CONSUMED:
        raise BrokerError("cycle already consumed", code="CYCLE_REPLAY")
    if existing.phase == BrokerPhase.PARKED_OWNER:
        raise BrokerError("owner-parked successor is not consumable", code="OWNER_PARKED")
    if existing.phase not in {BrokerPhase.QUEUED, BrokerPhase.FOLLOWUP_EMITTED}:
        raise BrokerError("successor is not consumable", code="CYCLE_NOT_READY")
    return persist_broker_state(
        store,
        existing.model_copy(
            update={
                "phase": BrokerPhase.CONSUMED,
                "consumed": True,
            }
        ),
    )


def recover_broker(root: Path) -> BrokerState | None:
    """Crash/restart: return durable state. Never mint a duplicate successor."""
    store = broker_store_dir(root)
    if not (store / CURRENT_NAME).is_file():
        return None
    return load_broker_state(store)


def render_broker_followup(state: BrokerState) -> str | None:
    """Fixed trusted template. Untrusted stop/envelope text never interpolates."""
    if state.phase not in {BrokerPhase.QUEUED, BrokerPhase.FOLLOWUP_EMITTED}:
        return None
    if state.consumed or state.cycle_id is None or state.kind is None:
        return None
    if state.followup_emitted:
        return None
    if not _CYCLE_RE.fullmatch(state.cycle_id):
        return None
    return (
        f"{BROKER_MARKER}\n"
        "\n"
        "Atlas CHECKPOINT_CONTINUE successor is queued.\n"
        "\n"
        f"Cycle: {state.cycle_id}\n"
        f"Kind: {state.kind.value}\n"
        f"Backend: {BACKEND}\n"
        "\n"
        "Worker/session terminal is not DAG terminal.\n"
        "Acknowledge is not authority.\n"
        "MERGE_AUTHORIZATION=NOT_GRANTED\n"
        "Do not create a second governor.\n"
        "Do not consume the 001C Cursor bridge slot.\n"
    )


def emit_stop_followup(root: Path) -> dict[str, str]:
    """Stop-hook backend. Never reads or writes the 001C bridge slot."""
    try:
        store = broker_store_dir(root)
        existing = load_broker_state(store)
    except BrokerError:
        return {}
    if existing is None:
        return {}
    message = render_broker_followup(existing)
    if message is None:
        return {}
    persist_broker_state(
        store,
        existing.model_copy(
            update={"phase": BrokerPhase.FOLLOWUP_EMITTED, "followup_emitted": True}
        ),
    )
    return {"followup_message": message}


def status_report(root: Path) -> dict[str, object]:
    try:
        existing = recover_broker(root)
    except BrokerError as exc:
        return {
            "ok": False,
            "error": exc.code,
            "package_id": PACKAGE_ID,
            "execution_authorized": False,
            "merge_authorized": False,
        }
    if existing is None:
        return {
            "ok": True,
            "package_id": PACKAGE_ID,
            "backend": BACKEND,
            "phase": BrokerPhase.IDLE.value,
            "execution_authorized": False,
            "merge_authorized": False,
        }
    return {
        "ok": True,
        "package_id": PACKAGE_ID,
        "backend": BACKEND,
        "phase": existing.phase.value,
        "cycle_id": existing.cycle_id,
        "kind": existing.kind.value if existing.kind else None,
        "followup_emitted": existing.followup_emitted,
        "consumed": existing.consumed,
        "owner_request_already_emitted": existing.owner_request_already_emitted,
        "execution_authorized": False,
        "merge_authorized": False,
        "authority_granted": False,
    }
