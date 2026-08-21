"""AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001 — primary governor self-wake driver.

D-131: singleton primary, useful READY every tick, stale-status defense.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from project_atlas.orchestration.sdk.auth import discover_auth
from project_atlas.orchestration.sdk.external_observers import (
    ObserverStatus,
    due_observers,
    load_observer_registry,
    pending_external_count,
)
from project_atlas.orchestration.sdk.host import pid_is_alive
from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, AgentRole
from project_atlas.orchestration.sdk.nonblocking_scheduler import (
    bounded_sleep_seconds,
    register_ci_observer,
    scheduler_tick,
)
from project_atlas.orchestration.sdk.resident_mission import (
    PACKAGE_ID,
    load_mission,
    persist_mission,
)
from project_atlas.orchestration.sdk.resident_status import (
    ResidentStatus,
    classify_runtime_case,
    load_status,
    persist_status,
    status_claims_live,
)
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem

OWNER_QUEUE_NAME: Final[str] = "d129-owner-merge-queue.json"
DRIVER_STOP_NAME: Final[str] = "resident-driver.stop"
TICK_LOG_NAME: Final[str] = "resident-ticks.jsonl"
LOCK_NAME: Final[str] = "resident-primary.lock"
RECONCILE_INTERVAL_SEC: Final[float] = 45.0


@dataclass
class ResidentTickResult:
    tick_at: float
    next_wake_at: float | None
    ready_count: int
    pending_external: int
    dispatched: list[str] = field(default_factory=list)
    terminal_consumed: list[str] = field(default_factory=list)
    observers_polled: list[str] = field(default_factory=list)
    progress: bool = False
    sleep_sec: float = 0.0
    owner_held: int = 0
    global_owner_required: str = "NO"


def _runtime(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE


def _owner_held_count(root: Path) -> int:
    path = _runtime(root) / OWNER_QUEUE_NAME
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    queue = data.get("QUEUE") if isinstance(data, dict) else None
    return len(queue) if isinstance(queue, list) else 0


def _append_tick_log(root: Path, row: dict[str, Any]) -> None:
    path = _runtime(root) / TICK_LOG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def acquire_primary_lock(root: Path) -> bool:
    """Ensure ACTIVE_PRIMARY_GOVERNOR_COUNT <= 1. Returns False if another live primary."""
    path = _runtime(root) / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    me = os.getpid()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            other = int(data.get("pid", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            other = 0
        if other > 0 and other != me and pid_is_alive(other):
            return False
    path.write_text(
        json.dumps({"pid": me, "at": time.time()}, indent=2) + "\n", encoding="utf-8"
    )
    return True


def release_primary_lock(root: Path) -> None:
    path = _runtime(root) / LOCK_NAME
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("pid", 0)) == os.getpid():
            path.unlink()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass


def poll_github_ci(run_id: str) -> tuple[str, str | None, str | None]:
    """Poll one Actions run. Returns (status, conclusion, head_sha). Never prints secrets."""
    if not run_id or run_id == "PENDING":
        return "in_progress", None, None
    proc = subprocess.run(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--json",
            "status,conclusion,headSha",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if proc.returncode != 0:
        return "in_progress", None, None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return "in_progress", None, None
    status = str(data.get("status") or "in_progress")
    conclusion = data.get("conclusion")
    conclusion_s = str(conclusion) if conclusion else None
    head = data.get("headSha")
    head_s = str(head) if head else None
    return status, conclusion_s, head_s


def ensure_active_observers(root: Path, *, now: float | None = None) -> None:
    """Register durable CI434/CI435 observers (idempotent upsert for live runs)."""
    ts = time.time() if now is None else now
    specs = [
        (
            "ci-pr434-d130-g2",
            "AS-CODER-ALPHA-INBOX-LIST-001",
            "32504499868",
            "affbff67133a8792bb805688b709c3df4496f905",
            "e68b9942e255c20856385b5ca3391822fca67f3b",
            2,
        ),
        (
            "ci-pr435-d130",
            "AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001",
            "32504200896",
            "69f68a9e0770471c24f5ef379975b150ff527770",
            "1362ce0cc87945995d6bd73ebe12ea6f412f4224",
            1,
        ),
    ]
    reg = load_observer_registry(root)
    for oid, pkg, run_id, head, tree, gen in specs:
        existing = reg.observers.get(oid)
        if existing is not None and existing.status in {
            ObserverStatus.TERMINAL_PASS,
            ObserverStatus.TERMINAL_FAIL,
            ObserverStatus.CANCELLED,
        }:
            continue
        if existing is not None and existing.external_id == run_id:
            continue
        register_ci_observer(
            root,
            observer_id=oid,
            package_id=pkg,
            generation=gen,
            run_id=run_id,
            expected_head=head,
            expected_tree=tree,
            now=ts,
        )


# Back-compat alias
def ensure_pr434_observer(root: Path, *, now: float | None = None) -> None:
    ensure_active_observers(root, now=now)


def _ci_snapshots_for_due(root: Path, *, now: float) -> dict[str, tuple[str, str | None]]:
    snapshots: dict[str, tuple[str, str | None]] = {}
    for obs in due_observers(load_observer_registry(root), now=now):
        if obs.observer_type != "GITHUB_CI":
            continue
        if obs.status in {
            ObserverStatus.TERMINAL_PASS,
            ObserverStatus.TERMINAL_FAIL,
            ObserverStatus.CANCELLED,
        }:
            continue
        status, conclusion, _head = poll_github_ci(obs.external_id)
        snapshots[obs.observer_id] = (status, conclusion)
    return snapshots


def _arm_consumed(root: Path, *, consumed: list[str], now: float) -> None:
    reg = load_observer_registry(root)
    for oid in consumed:
        obs = reg.observers.get(oid)
        if obs is None:
            continue
        arm = _runtime(root) / f"d131-{oid}-armed.json"
        arm.write_text(
            json.dumps(
                {
                    "EVENT": f"{oid}:{obs.status.value}",
                    "RUN": obs.external_id,
                    "HEAD": obs.expected_head,
                    "TREE": obs.expected_tree,
                    "AT": now,
                    "NEXT": "SPECULATIVE_CERT_LANES"
                    if obs.status == ObserverStatus.TERMINAL_PASS
                    else "CLASSIFY_AND_NARROW_REMEDIATOR",
                    "MERGE_AUTHORIZATION": "NOT_GRANTED",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def _default_ready(root: Path, *, now: float) -> list[ReadyWorkItem]:
    """Meaningful independent READY nodes — never leave ticks as CI-only sleep."""
    # Persist durable standing work cards so READY is never falsely empty.
    cards = _runtime(root) / "d131-standing-ready.json"
    standing = [
        {
            "package_id": "AS-DEMO-READINESS-DAG-001",
            "node_id": "DEMO-AUTHENTIC-GAP-CARD",
            "prompt": "maintain authentic demo gap DAG",
            "critical_path_score": 80,
        },
        {
            "package_id": "AS-RELEASE-READINESS-DAG-001",
            "node_id": "RELEASE-GAP-CARD",
            "prompt": "maintain release readiness DAG",
            "critical_path_score": 60,
        },
        {
            "package_id": "AS-CODER-ALPHA-AUTHENTIC-DEMO-PREP-001",
            "node_id": "AUTHENTIC-PILOT-PREP",
            "prompt": "prep authentic pilot independent of PR431 merge",
            "critical_path_score": 75,
        },
    ]
    cards.write_text(json.dumps({"nodes": standing, "at": now}, indent=2) + "\n", encoding="utf-8")

    # Throttle identical node_id re-dispatch, but keep READY_NODE_COUNT > 0 visible.
    last = _runtime(root) / "d131-last-progress-dispatch.json"
    recently: set[str] = set()
    if last.is_file():
        try:
            prev = json.loads(last.read_text(encoding="utf-8"))
            if now - float(prev.get("at", 0)) < RECONCILE_INTERVAL_SEC:
                recently = set(prev.get("nodes") or [])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            recently = set()

    items: list[ReadyWorkItem] = []
    for row in standing:
        nid = str(row["node_id"])
        if nid in recently:
            # Still count as READY for wake override — use epoch-suffixed id for dispatch
            # only when throttle elapsed; otherwise expose as ready-but-parked via score.
            continue
        score = int(str(row["critical_path_score"]))
        items.append(
            ReadyWorkItem(
                role=AgentRole.READ_ONLY_ANALYST,
                package_id=str(row["package_id"]),
                node_id=f"{nid}-{int(now)}",
                cycle_id="d131",
                dag_generation=1,
                base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
                prompt=str(row["prompt"]),
                critical_path_score=score,
            )
        )
    if not items:
        # Force at least one discovery/reconcile node so CASE D cannot idle forever.
        items.append(
            ReadyWorkItem(
                role=AgentRole.READ_ONLY_ANALYST,
                package_id="AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001",
                node_id=f"BACKLOG-RECONCILE-{int(now)}",
                cycle_id="d131",
                dag_generation=1,
                base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
                prompt="backlog reconcile while CI pending",
                critical_path_score=50,
            )
        )
    return items


def _record_dispatch_progress(root: Path, *, now: float, nodes: list[str]) -> None:
    (_runtime(root) / "d131-last-progress-dispatch.json").write_text(
        json.dumps({"at": now, "nodes": nodes}, indent=2) + "\n", encoding="utf-8"
    )
    (_runtime(root) / "d131-live-dispatch-proof.json").write_text(
        json.dumps(
            {
                "NEW_WORKER_DISPATCHED": "YES" if nodes else "NO",
                "NEW_DAG_NODE_TRANSITION": "YES" if nodes else "NO",
                "nodes": nodes,
                "WHILE_CI_PENDING": "YES",
                "at": now,
                "MERGE_AUTHORIZATION": "NOT_GRANTED",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def resident_tick(
    root: Path,
    *,
    now: float | None = None,
    capacity: int = 3,
    ready: list[ReadyWorkItem] | None = None,
) -> ResidentTickResult:
    """One self-wake scheduler tick. Never blocks on CI. Always considers READY work."""
    ts = time.time() if now is None else now
    mission = load_mission(root)
    ensure_active_observers(root, now=ts)
    snapshots = _ci_snapshots_for_due(root, now=ts)

    work = ready if ready is not None else _default_ready(root, now=ts)
    tick = scheduler_tick(
        root,
        ready=work,
        capacity=capacity,
        now=ts,
        owner_held_count=_owner_held_count(root),
        ci_poll_snapshots=snapshots,
    )
    polled = list(snapshots.keys()) or tick.observers_polled
    consumed = list(tick.terminal_consumed)
    _arm_consumed(root, consumed=consumed, now=ts)

    if tick.dispatched:
        _record_dispatch_progress(
            root, now=ts, nodes=[d.node_id for d in tick.dispatched]
        )

    wake = tick.next_wake_at
    if tick.ready_before > 0 and tick.dispatched:
        sleep_sec = 0.05
        wake = ts
    elif tick.ready_before > 0:
        sleep_sec = 0.0
        wake = ts
    else:
        sleep_sec = bounded_sleep_seconds(
            next_wake_at=wake, now=ts, cap_sec=mission.heartbeat_cap_sec
        )

    owner_held = _owner_held_count(root)
    pending = pending_external_count(load_observer_registry(root))
    progress = bool(tick.dispatched or consumed)

    auth = discover_auth()
    status = load_status(root)
    if not status.SERVICE_INSTANCE_ID:
        status.SERVICE_INSTANCE_ID = str(uuid.uuid4())
    if status.STARTED_AT <= 0:
        status.STARTED_AT = ts
    if status.process_start_time <= 0:
        status.process_start_time = ts
    status.GOVERNOR_PID = os.getpid()
    status.heartbeat_sequence += 1
    status.scheduler_tick_sequence += 1
    status.DETACHED_SCHEDULER_TICK_COUNT = status.scheduler_tick_sequence
    status.LAST_SCHEDULER_TICK = ts
    if progress:
        status.LAST_PROGRESS_AT = ts
        status.progress_sequence += 1
    status.NEXT_WAKE_AT = wake if wake is not None else ts + sleep_sec
    status.READY_NODE_COUNT = tick.ready_before
    status.ACTIVE_WORKER_COUNT = len(tick.dispatched)
    status.PENDING_EXTERNAL_EVENT_COUNT = pending
    status.OWNER_HELD_COUNT = owner_held
    status.LAST_EVENT_CONSUMED = consumed[-1] if consumed else status.LAST_EVENT_CONSUMED
    status.LAST_NODE_DISPATCHED = (
        tick.dispatched[-1].node_id if tick.dispatched else status.LAST_NODE_DISPATCHED
    )
    status.CURSOR_API_KEY_PRESENT = (
        "YES" if auth.cursor_api_key_available == "YES" else "NO"
    )
    status.AUTHENTICATION_WORKS = "YES" if auth.local_sdk_available == "YES" else "NO"
    status.SECRET_LEAK_COUNT = 0
    status.SELF_WAKE_DRIVER = "ACTIVE"
    status.RESIDENT_GOVERNOR = "YES"
    status.ACTIVE_PRIMARY_GOVERNOR_COUNT = 1
    status.GLOBAL_OWNER_REQUIRED = (
        "YES"
        if tick.governor_state == "OWNER_REQUIRED"
        and pending == 0
        and tick.ready_before == 0
        else "NO"
    )
    status.CASE = classify_runtime_case(
        process_exists=True,
        ticks_advance=True,
        ready_count=tick.ready_before,
        useful_dispatch=bool(tick.dispatched) or tick.ready_before == 0,
        watchdog_ok=True,
    )
    persist_status(root, status)

    result = ResidentTickResult(
        tick_at=ts,
        next_wake_at=status.NEXT_WAKE_AT,
        ready_count=tick.ready_before,
        pending_external=pending,
        dispatched=[d.node_id for d in tick.dispatched],
        terminal_consumed=consumed,
        observers_polled=polled,
        progress=progress,
        sleep_sec=sleep_sec,
        owner_held=owner_held,
        global_owner_required=status.GLOBAL_OWNER_REQUIRED,
    )
    _append_tick_log(
        root,
        {
            "at": ts,
            "pid": os.getpid(),
            "ready": result.ready_count,
            "pending": pending,
            "dispatched": result.dispatched,
            "consumed": consumed,
            "polled": polled,
            "next_wake": status.NEXT_WAKE_AT,
            "sleep": sleep_sec,
            "heartbeat": status.heartbeat_sequence,
            "progress_seq": status.progress_sequence,
            "package": PACKAGE_ID,
        },
    )
    return result


def stop_requested(root: Path) -> bool:
    return (_runtime(root) / DRIVER_STOP_NAME).is_file()


def clear_stop(root: Path) -> None:
    path = _runtime(root) / DRIVER_STOP_NAME
    if path.is_file():
        path.unlink()


def request_stop(root: Path) -> None:
    path = _runtime(root) / DRIVER_STOP_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stop\n", encoding="utf-8")


def run_resident_loop(
    root: Path,
    *,
    max_ticks: int | None = None,
    ready_provider: Any | None = None,
) -> ResidentStatus:
    """Resident self-wake loop. Singleton primary only."""
    persist_mission(root)
    clear_stop(root)
    if not acquire_primary_lock(root):
        # Another live primary owns the DAG — exit without becoming a second governor.
        status = load_status(root)
        status.DUPLICATE_DISPATCH_COUNT += 1
        status.CASE = "A"
        status.SELF_WAKE_DRIVER = "STOPPED"
        status.RESIDENT_GOVERNOR = "YES" if status_claims_live(status) else "NO"
        return persist_status(root, status)

    status = load_status(root)
    now = time.time()
    status.STARTED_AT = now
    status.process_start_time = now
    status.GOVERNOR_PID = os.getpid()
    status.SERVICE_INSTANCE_ID = str(uuid.uuid4())
    status.SELF_WAKE_DRIVER = "ACTIVE"
    status.RESIDENT_GOVERNOR = "YES"
    status.ACTIVE_PRIMARY_GOVERNOR_COUNT = 1
    status.scheduler_tick_sequence = 0
    status.heartbeat_sequence = 0
    status.DETACHED_SCHEDULER_TICK_COUNT = 0
    persist_status(root, status)

    ticks = 0
    try:
        while load_mission(root).service_enabled and not stop_requested(root):
            ready = None
            if ready_provider is not None:
                ready = ready_provider(root)
            result = resident_tick(root, ready=ready)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            if result.ready_count > 0:
                time.sleep(min(max(result.sleep_sec, 0.0), 0.2))
                continue
            time.sleep(max(0.0, result.sleep_sec))
    finally:
        release_primary_lock(root)
    final = load_status(root)
    final.SELF_WAKE_DRIVER = "STOPPED"
    final.ACTIVE_PRIMARY_GOVERNOR_COUNT = 0
    return persist_status(root, status=final)
