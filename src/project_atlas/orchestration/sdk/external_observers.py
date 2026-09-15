"""Durable external observers — PENDING_EXTERNAL_EVENT != GLOBAL_SCHEDULER_BLOCK.

AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001 / D-128.

Observers have NO merge authority. They are polled/consumed by scheduler ticks;
they never cause a global blocking wait.
"""

from __future__ import annotations

import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, SdkRuntimeError

PACKAGE_ID: Final[Literal["AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001"]] = (
    "AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001"
)
OBSERVERS_NAME: Final[str] = "external-observers.json"
LIVENESS_NAME: Final[str] = "scheduler-liveness.json"
CONSUMED_EVENTS_NAME: Final[str] = "external-observer-consumed.json"

ObserverType = Literal[
    "GITHUB_CI",
    "CURSOR_CLOUD_RUN",
    "LOCAL_WORKER",
    "REMOTE_SMOKE",
    "RETRY_TIMER",
]


class ObserverStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    TERMINAL_PASS = "TERMINAL_PASS"
    TERMINAL_FAIL = "TERMINAL_FAIL"
    PARKED = "PARKED"
    CANCELLED = "CANCELLED"


_TERMINAL: Final[frozenset[ObserverStatus]] = frozenset(
    {
        ObserverStatus.TERMINAL_PASS,
        ObserverStatus.TERMINAL_FAIL,
        ObserverStatus.CANCELLED,
    }
)


class ExternalObserver(BaseModel):
    """One durable external wait. Not authority."""

    model_config = ConfigDict(extra="forbid")

    observer_id: str = Field(min_length=1, max_length=256)
    observer_type: ObserverType
    package_id: str = Field(min_length=1, max_length=256)
    generation: int = Field(ge=0, le=1_000_000)
    external_id: str = Field(min_length=1, max_length=256)
    expected_head: str | None = None
    expected_tree: str | None = None
    created_at: float
    next_poll_at: float
    retry_count: int = Field(default=0, ge=0)
    status: ObserverStatus = ObserverStatus.PENDING
    last_error: str | None = None
    merge_authorized: Literal[False] = False

    @field_validator("observer_id", "package_id", "external_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise SdkRuntimeError("observer field blank", code="OBSERVER_INVALID")
        return value


class ObserverRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001"] = PACKAGE_ID
    observers: dict[str, ExternalObserver] = Field(default_factory=dict)
    merge_authorized: Literal[False] = False


class SchedulerLiveness(BaseModel):
    """Observability only — not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    GOVERNOR_STATE: Literal[
        "ACTIVE",
        "BOUNDED_IDLE",
        "OWNER_REQUIRED",
        "PROJECT_IDLE",
        "STALL_RECONCILING",
    ] = "ACTIVE"
    LAST_SCHEDULER_TICK: float = 0.0
    LAST_PROGRESS_AT: float = 0.0
    READY_NODE_COUNT: int = 0
    RUNNING_NODE_COUNT: int = 0
    PENDING_EXTERNAL_EVENT_COUNT: int = 0
    PARKED_NODE_COUNT: int = 0
    OWNER_HELD_COUNT: int = 0
    ACTIVE_WORKER_COUNT: int = 0
    NEXT_WAKE_AT: float | None = None
    SCHEDULER_STALL_DETECTED: bool = False
    GLOBAL_BLOCKING_CI_WAIT_COUNT: int = 0
    GLOBAL_BLOCKING_WORKER_WAIT_COUNT: int = 0
    merge_authorized: Literal[False] = False


def observers_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / OBSERVERS_NAME


def liveness_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / LIVENESS_NAME


def consumed_events_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / CONSUMED_EVENTS_NAME


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_observer_registry(root: Path) -> ObserverRegistry:
    path = observers_path(root)
    if not path.is_file():
        return ObserverRegistry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ObserverRegistry()
    if not isinstance(data, dict):
        return ObserverRegistry()
    data["merge_authorized"] = False
    return ObserverRegistry.model_validate(data)


def persist_observer_registry(root: Path, registry: ObserverRegistry) -> None:
    payload = registry.model_dump(mode="json")
    payload["merge_authorized"] = False
    _atomic_write(observers_path(root), payload)


def load_liveness(root: Path) -> SchedulerLiveness:
    path = liveness_path(root)
    if not path.is_file():
        return SchedulerLiveness()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SchedulerLiveness()
    if not isinstance(data, dict):
        return SchedulerLiveness()
    data["merge_authorized"] = False
    return SchedulerLiveness.model_validate(data)


def persist_liveness(root: Path, liveness: SchedulerLiveness) -> None:
    payload = liveness.model_dump(mode="json")
    payload["merge_authorized"] = False
    _atomic_write(liveness_path(root), payload)


def load_consumed_event_ids(root: Path) -> set[str]:
    path = consumed_events_path(root)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = data.get("consumed") if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return set()
    return {str(x) for x in ids}


def persist_consumed_event_ids(root: Path, ids: set[str]) -> None:
    _atomic_write(
        consumed_events_path(root),
        {"consumed": sorted(ids), "merge_authorized": False},
    )


def register_observer(
    root: Path,
    observer: ExternalObserver,
    *,
    now: float | None = None,
) -> ExternalObserver:
    """Register or idempotently refresh an observer. Never grants merge."""
    _ = now
    if observer.merge_authorized is not False:
        raise SdkRuntimeError("observer cannot grant merge", code="OBSERVER_NO_MERGE")
    registry = load_observer_registry(root)
    existing = registry.observers.get(observer.observer_id)
    if existing is not None and existing.status in _TERMINAL:
        # Terminal observers are immutable except cancel already terminal.
        return existing
    registry.observers[observer.observer_id] = observer.model_copy(
        update={"merge_authorized": False}
    )
    persist_observer_registry(root, registry)
    return registry.observers[observer.observer_id]


def update_observer_status(
    root: Path,
    observer_id: str,
    *,
    status: ObserverStatus,
    next_poll_at: float | None = None,
    retry_count: int | None = None,
    last_error: str | None = None,
) -> ExternalObserver:
    registry = load_observer_registry(root)
    current = registry.observers.get(observer_id)
    if current is None:
        raise SdkRuntimeError(f"unknown observer {observer_id}", code="OBSERVER_UNKNOWN")
    if current.status in _TERMINAL and status not in _TERMINAL:
        raise SdkRuntimeError(
            "cannot resurrect terminal observer",
            code="OBSERVER_TERMINAL",
        )
    updates: dict[str, object] = {"status": status, "merge_authorized": False}
    if next_poll_at is not None:
        updates["next_poll_at"] = next_poll_at
    if retry_count is not None:
        updates["retry_count"] = retry_count
    if last_error is not None:
        updates["last_error"] = last_error
    updated = current.model_copy(update=updates)
    registry.observers[observer_id] = updated
    persist_observer_registry(root, registry)
    return updated


def due_observers(registry: ObserverRegistry, *, now: float) -> list[ExternalObserver]:
    """Observers eligible for a nonblocking poll this tick."""
    return [
        obs
        for obs in registry.observers.values()
        if obs.status not in _TERMINAL and obs.next_poll_at <= now
    ]


def pending_external_count(registry: ObserverRegistry) -> int:
    return sum(1 for o in registry.observers.values() if o.status not in _TERMINAL)


def nearest_wake_at(registry: ObserverRegistry) -> float | None:
    times = [
        o.next_poll_at
        for o in registry.observers.values()
        if o.status not in _TERMINAL
    ]
    return min(times) if times else None


def consume_terminal_event(
    root: Path,
    *,
    observer_id: str,
    event_key: str,
) -> bool:
    """Idempotent terminal-event consumption. Returns True if first accept."""
    registry = load_observer_registry(root)
    obs = registry.observers.get(observer_id)
    if obs is None:
        raise SdkRuntimeError(f"unknown observer {observer_id}", code="OBSERVER_UNKNOWN")
    if obs.status not in {
        ObserverStatus.TERMINAL_PASS,
        ObserverStatus.TERMINAL_FAIL,
        ObserverStatus.CANCELLED,
    }:
        raise SdkRuntimeError(
            "observer not terminal",
            code="OBSERVER_NOT_TERMINAL",
        )
    consumed = load_consumed_event_ids(root)
    if event_key in consumed:
        return False
    consumed.add(event_key)
    persist_consumed_event_ids(root, consumed)
    return True


def park_observer_backoff(
    root: Path,
    observer_id: str,
    *,
    now: float | None = None,
    error: str = "TRANSIENT",
) -> ExternalObserver:
    """Park observer with exponential backoff. Resource yield — not owner."""
    ts = time.time() if now is None else now
    registry = load_observer_registry(root)
    current = registry.observers.get(observer_id)
    if current is None:
        raise SdkRuntimeError(f"unknown observer {observer_id}", code="OBSERVER_UNKNOWN")
    attempt = current.retry_count + 1
    delay = min(300.0, 2.0 ** min(attempt, 8))
    return update_observer_status(
        root,
        observer_id,
        status=ObserverStatus.PARKED,
        next_poll_at=ts + delay,
        retry_count=attempt,
        last_error=error,
    )


def make_observer(
    *,
    observer_id: str,
    observer_type: ObserverType,
    package_id: str,
    generation: int,
    external_id: str,
    expected_head: str | None = None,
    expected_tree: str | None = None,
    now: float | None = None,
    poll_after_sec: float = 0.0,
    status: ObserverStatus = ObserverStatus.PENDING,
) -> ExternalObserver:
    ts = time.time() if now is None else now
    return ExternalObserver(
        observer_id=observer_id,
        observer_type=observer_type,
        package_id=package_id,
        generation=generation,
        external_id=external_id,
        expected_head=expected_head,
        expected_tree=expected_tree,
        created_at=ts,
        next_poll_at=ts + poll_after_sec,
        status=status,
        merge_authorized=False,
    )
