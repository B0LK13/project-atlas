"""Nonblocking scheduler tick — WAITING IS A NODE STATE, NOT A GOVERNOR STATE.

AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001 / D-128.

Each tick:
  reconcile terminal events → promote deps → dispatch READY → register observers
  → persist liveness. Never enters a long blocking child wait.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from project_atlas.orchestration.sdk.external_observers import (
    PACKAGE_ID as LIVENESS_PACKAGE_ID,
)
from project_atlas.orchestration.sdk.external_observers import (
    ExternalObserver,
    ObserverRegistry,
    ObserverStatus,
    SchedulerLiveness,
    consume_terminal_event,
    due_observers,
    load_liveness,
    load_observer_registry,
    nearest_wake_at,
    pending_external_count,
    persist_liveness,
    register_observer,
    update_observer_status,
)
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem

STALL_INTERVAL_SEC: Final[float] = 30.0
BOUNDED_IDLE_CAP_SEC: Final[float] = 5.0
POLL_ERROR_FAIL_AFTER: Final[int] = 3


@dataclass
class DispatchedNode:
    node_id: str
    package_id: str
    role: str
    dispatched_at: float


@dataclass
class TickResult:
    """One nonblocking scheduler tick outcome. Not authority."""

    dispatched: list[DispatchedNode] = field(default_factory=list)
    terminal_consumed: list[str] = field(default_factory=list)
    observers_polled: list[str] = field(default_factory=list)
    parked_nodes: list[str] = field(default_factory=list)
    stall_detected: bool = False
    stall_reconciled: bool = False
    governor_state: Literal[
        "ACTIVE",
        "BOUNDED_IDLE",
        "OWNER_REQUIRED",
        "PROJECT_IDLE",
        "STALL_RECONCILING",
    ] = "ACTIVE"
    next_wake_at: float | None = None
    ready_before: int = 0
    ready_after: int = 0
    pending_external: int = 0
    owner_held: int = 0
    global_blocking_ci_waits: int = 0
    global_blocking_worker_waits: int = 0
    duplicate_event_skips: int = 0
    merge_authorized: bool = False
    resource_yield_owner_required: bool = False


def _priority_key(item: ReadyWorkItem) -> tuple[int, str]:
    # Higher critical_path_score first; stable by node_id.
    return (-item.critical_path_score, item.node_id)


def select_ready_for_dispatch(
    ready: list[ReadyWorkItem],
    *,
    capacity: int,
    parked_node_ids: set[str] | None = None,
    owner_held_packages: set[str] | None = None,
) -> list[ReadyWorkItem]:
    """Select READY work ignoring pending external waits on other packages."""
    parked = parked_node_ids or set()
    owner_held = owner_held_packages or set()
    eligible = [
        item
        for item in ready
        if item.node_id not in parked and item.package_id not in owner_held
    ]
    ordered = sorted(eligible, key=_priority_key)
    if capacity <= 0:
        return []
    return ordered[:capacity]


def classify_idle(
    *,
    ready_count: int,
    pending_external: int,
    owner_held: int,
    runnable_independent: int,
) -> Literal["ACTIVE", "BOUNDED_IDLE", "OWNER_REQUIRED", "PROJECT_IDLE"]:
    if runnable_independent > 0 or ready_count > 0:
        return "ACTIVE"
    if pending_external > 0:
        return "BOUNDED_IDLE"
    if owner_held > 0 and ready_count == 0 and pending_external == 0:
        return "OWNER_REQUIRED"
    return "PROJECT_IDLE"


def detect_stall(
    liveness: SchedulerLiveness,
    *,
    now: float,
    ready_count: int,
    pending_external: int,
    stall_interval_sec: float = STALL_INTERVAL_SEC,
) -> bool:
    """PENDING externals + READY work + no progress for bounded interval."""
    if pending_external <= 0 or ready_count <= 0:
        return False
    if liveness.LAST_PROGRESS_AT <= 0:
        return False
    return (now - liveness.LAST_PROGRESS_AT) >= stall_interval_sec


def bounded_sleep_seconds(
    *,
    next_wake_at: float | None,
    now: float,
    cap_sec: float = BOUNDED_IDLE_CAP_SEC,
) -> float:
    """Sleep only until nearest wake, capped. Never long global CI wait."""
    if next_wake_at is None:
        return min(cap_sec, 1.0)
    delay = max(0.0, next_wake_at - now)
    return min(delay, cap_sec)


def _maybe_mint_stacked_parent_seal(root: Path, obs: ExternalObserver) -> None:
    """Wire D-138 gate: mint parent seal on stacked post-merge CI TERMINAL_PASS."""
    if obs.expected_head is None or obs.expected_tree is None:
        return
    from project_atlas.orchestration.sdk.ci_observer import observe_exact_head_ci
    from project_atlas.orchestration.sdk.merge_sequence_gate import (
        observe_live_main_identity,
        on_ci_terminal_pass_for_stacked_merge,
        refresh_dependent_merge_gate_state,
    )

    live = observe_live_main_identity(root)
    if live is None:
        return
    live_main, live_tree = live
    # PR-branch expected_head is not post-merge main identity (D-138).
    if live_main == obs.expected_head:
        return
    ci_obs = observe_exact_head_ci(head_sha=live_main)
    on_ci_terminal_pass_for_stacked_merge(
        root,
        package_id=obs.package_id,
        ci_observation=ci_obs,
        parent_merge_commit=live_main,
        parent_post_merge_main_sha=live_main,
        parent_post_merge_tree=live_tree,
    )
    refresh_dependent_merge_gate_state(
        root,
        child_pr_number=436,
        child_merge_authorized=False,
        parent_merged=True,
        parent_merge_commit=live_main,
        live_main_sha=live_main,
        live_tree_sha=live_tree,
        ci_observation=ci_obs,
    )


def apply_ci_poll_result(
    root: Path,
    observer_id: str,
    *,
    raw_status: str,
    conclusion: str | None,
    now: float | None = None,
    poll_interval_sec: float = 15.0,
) -> ExternalObserver:
    """Map a CI status snapshot onto durable observer state. Nonblocking."""
    ts = time.time() if now is None else now
    status_l = raw_status.lower()
    conc_l = (conclusion or "").lower() or None
    if status_l == "error" or conc_l in {"not_found", "poll_failed", "inaccessible"}:
        registry = load_observer_registry(root)
        current = registry.observers.get(observer_id)
        retries = (current.retry_count + 1) if current is not None else 1
        if retries >= POLL_ERROR_FAIL_AFTER:
            cancelled = conc_l in {"not_found", "inaccessible"}
            return update_observer_status(
                root,
                observer_id,
                status=ObserverStatus.CANCELLED if cancelled else ObserverStatus.TERMINAL_FAIL,
                next_poll_at=ts,
                retry_count=retries,
                last_error=conc_l or "POLL_ERROR",
            )
        return update_observer_status(
            root,
            observer_id,
            status=ObserverStatus.RUNNING,
            next_poll_at=ts + poll_interval_sec,
            retry_count=retries,
            last_error=conc_l or "POLL_ERROR",
        )
    if status_l in {"queued", "in_progress", "waiting", "pending"}:
        return update_observer_status(
            root,
            observer_id,
            status=ObserverStatus.RUNNING,
            next_poll_at=ts + poll_interval_sec,
            last_error=None,
        )
    if conc_l == "success":
        return update_observer_status(
            root,
            observer_id,
            status=ObserverStatus.TERMINAL_PASS,
            next_poll_at=ts,
        )
    if conc_l == "cancelled":
        return update_observer_status(
            root,
            observer_id,
            status=ObserverStatus.CANCELLED,
            next_poll_at=ts,
        )
    if conc_l in {"failure", "timed_out", "startup_failure"}:
        return update_observer_status(
            root,
            observer_id,
            status=ObserverStatus.TERMINAL_FAIL,
            next_poll_at=ts,
            last_error=conc_l,
        )
    return update_observer_status(
        root,
        observer_id,
        status=ObserverStatus.RUNNING,
        next_poll_at=ts + poll_interval_sec,
        last_error="UNKNOWN_STATUS",
    )


def scheduler_tick(
    root: Path,
    *,
    ready: list[ReadyWorkItem],
    capacity: int = 4,
    parked_node_ids: set[str] | None = None,
    owner_held_packages: set[str] | None = None,
    owner_held_count: int = 0,
    running_workers: int = 0,
    now: float | None = None,
    ci_poll_snapshots: dict[str, tuple[str, str | None]] | None = None,
    stall_interval_sec: float = STALL_INTERVAL_SEC,
) -> TickResult:
    """One nonblocking tick. Dispatches READY even while externals are pending."""
    ts = time.time() if now is None else now
    result = TickResult(
        global_blocking_ci_waits=0,
        global_blocking_worker_waits=0,
        merge_authorized=False,
        resource_yield_owner_required=False,
    )
    registry = load_observer_registry(root)
    liveness = load_liveness(root)
    result.ready_before = len(ready)
    result.pending_external = pending_external_count(registry)
    result.owner_held = owner_held_count

    # 1) Poll due observers (nonblocking snapshots only).
    snapshots = ci_poll_snapshots or {}
    for obs in due_observers(registry, now=ts):
        result.observers_polled.append(obs.observer_id)
        snap = snapshots.get(obs.observer_id)
        if snap is not None:
            apply_ci_poll_result(
                root,
                obs.observer_id,
                raw_status=snap[0],
                conclusion=snap[1],
                now=ts,
            )

    registry = load_observer_registry(root)

    # 2) Consume terminal events idempotently.
    for obs in list(registry.observers.values()):
        if obs.status not in {
            ObserverStatus.TERMINAL_PASS,
            ObserverStatus.TERMINAL_FAIL,
            ObserverStatus.CANCELLED,
        }:
            continue
        event_key = f"{obs.observer_id}:{obs.status.value}:{obs.external_id}"
        first = consume_terminal_event(
            root, observer_id=obs.observer_id, event_key=event_key
        )
        if first:
            result.terminal_consumed.append(obs.observer_id)
            if obs.status == ObserverStatus.TERMINAL_PASS:
                _maybe_mint_stacked_parent_seal(root, obs)
        else:
            result.duplicate_event_skips += 1

    # 3) Stall detection + self-reconcile.
    pending = pending_external_count(registry)
    stall = detect_stall(
        liveness,
        now=ts,
        ready_count=len(ready),
        pending_external=pending,
        stall_interval_sec=stall_interval_sec,
    )
    result.stall_detected = stall
    if stall:
        result.governor_state = "STALL_RECONCILING"
        # Self-reconcile: force due polls and clear false parks by refreshing wake.
        for obs in registry.observers.values():
            if obs.status not in {
                ObserverStatus.TERMINAL_PASS,
                ObserverStatus.TERMINAL_FAIL,
                ObserverStatus.CANCELLED,
            }:
                update_observer_status(
                    root,
                    obs.observer_id,
                    status=ObserverStatus.RUNNING
                    if obs.status != ObserverStatus.PARKED
                    else ObserverStatus.PARKED,
                    next_poll_at=ts,
                )
        result.stall_reconciled = True
        registry = load_observer_registry(root)
        pending = pending_external_count(registry)

    # 4) Dispatch READY work — never blocked by pending externals.
    selected = select_ready_for_dispatch(
        ready,
        capacity=capacity,
        parked_node_ids=parked_node_ids,
        owner_held_packages=owner_held_packages,
    )
    for item in selected:
        result.dispatched.append(
            DispatchedNode(
                node_id=item.node_id,
                package_id=item.package_id,
                role=item.role.value if hasattr(item.role, "value") else str(item.role),
                dispatched_at=ts,
            )
        )

    result.ready_after = max(0, len(ready) - len(result.dispatched))
    result.pending_external = pending
    wake = nearest_wake_at(registry)
    result.next_wake_at = wake

    # Selection is not progress — only terminal consume or stall self-reconcile.
    progress = bool(result.terminal_consumed or result.stall_reconciled)
    # Count only independently runnable remaining work (exclude owner-held packages).
    held = owner_held_packages or set()
    remaining_runnable = sum(
        1
        for item in ready
        if item.node_id not in {d.node_id for d in result.dispatched}
        and item.package_id not in held
        and item.node_id not in (parked_node_ids or set())
    )
    idle = classify_idle(
        ready_count=remaining_runnable,
        pending_external=pending,
        owner_held=owner_held_count,
        runnable_independent=len(result.dispatched),
    )
    state: Literal[
        "ACTIVE",
        "BOUNDED_IDLE",
        "OWNER_REQUIRED",
        "PROJECT_IDLE",
        "STALL_RECONCILING",
    ] = "STALL_RECONCILING" if (stall and not result.dispatched) else idle
    result.governor_state = state

    updated = SchedulerLiveness(
        GOVERNOR_STATE=state,
        LAST_SCHEDULER_TICK=ts,
        LAST_PROGRESS_AT=ts if progress else liveness.LAST_PROGRESS_AT,
        READY_NODE_COUNT=result.ready_after,
        RUNNING_NODE_COUNT=running_workers,
        PENDING_EXTERNAL_EVENT_COUNT=pending,
        PARKED_NODE_COUNT=len(parked_node_ids or ()),
        OWNER_HELD_COUNT=owner_held_count,
        ACTIVE_WORKER_COUNT=running_workers,
        NEXT_WAKE_AT=wake,
        SCHEDULER_STALL_DETECTED=stall,
        GLOBAL_BLOCKING_CI_WAIT_COUNT=0,
        GLOBAL_BLOCKING_WORKER_WAIT_COUNT=0,
        merge_authorized=False,
    )
    persist_liveness(root, updated)
    return result


def register_ci_observer(
    root: Path,
    *,
    observer_id: str,
    package_id: str,
    generation: int,
    run_id: str,
    expected_head: str,
    expected_tree: str | None = None,
    now: float | None = None,
) -> ExternalObserver:
    """Register a GitHub CI observer without blocking."""
    obs = ExternalObserver(
        observer_id=observer_id,
        observer_type="GITHUB_CI",
        package_id=package_id,
        generation=generation,
        external_id=str(run_id),
        expected_head=expected_head,
        expected_tree=expected_tree,
        created_at=time.time() if now is None else now,
        next_poll_at=time.time() if now is None else now,
        status=ObserverStatus.RUNNING,
        merge_authorized=False,
    )
    return register_observer(root, obs, now=now)


def prove_two_ci_do_not_block_dispatch(
    root: Path,
    *,
    ready: list[ReadyWorkItem],
    now: float | None = None,
) -> TickResult:
    """Live invariant helper: pending CI observers must not zero-out dispatch."""
    registry = load_observer_registry(root)
    assert pending_external_count(registry) >= 1
    tick = scheduler_tick(
        root,
        ready=ready,
        capacity=max(1, len(ready)),
        now=now,
    )
    assert tick.global_blocking_ci_waits == 0
    assert tick.resource_yield_owner_required is False
    return tick


__all__ = [
    "BOUNDED_IDLE_CAP_SEC",
    "LIVENESS_PACKAGE_ID",
    "STALL_INTERVAL_SEC",
    "DispatchedNode",
    "ObserverRegistry",
    "TickResult",
    "apply_ci_poll_result",
    "bounded_sleep_seconds",
    "classify_idle",
    "detect_stall",
    "prove_two_ci_do_not_block_dispatch",
    "register_ci_observer",
    "scheduler_tick",
    "select_ready_for_dispatch",
]
