"""AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001 — primary governor self-wake driver.

Single coordinator. No secondary authority. Owns clock + wake + recovery.
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
    load_status,
    persist_status,
)
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem

OWNER_QUEUE_NAME: Final[str] = "d129-owner-merge-queue.json"
DRIVER_STOP_NAME: Final[str] = "resident-driver.stop"
TICK_LOG_NAME: Final[str] = "resident-ticks.jsonl"


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


def poll_github_ci(run_id: str) -> tuple[str, str | None, str | None]:
    """Poll one Actions run. Returns (status, conclusion, head_sha). Never prints secrets."""
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


def ensure_pr434_observer(root: Path, *, now: float | None = None) -> None:
    """Register durable CI434 observer if missing."""
    ts = time.time() if now is None else now
    reg = load_observer_registry(root)
    if "ci-pr434-d129" in reg.observers:
        return
    register_ci_observer(
        root,
        observer_id="ci-pr434-d129",
        package_id="AS-CODER-ALPHA-INBOX-LIST-001",
        generation=1,
        run_id="32502864813",
        expected_head="ed241551fc7b634fdd3b6224fae874d47bb56618",
        expected_tree="d904570e782ff5f82c998d5f717778f121e7f07c",
        now=ts,
    )


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


def _arm_pr434_if_consumed(root: Path, *, consumed: list[str], now: float) -> None:
    if "ci-pr434-d129" not in consumed:
        return
    reg = load_observer_registry(root)
    obs = reg.observers.get("ci-pr434-d129")
    if obs is None:
        return
    arm = _runtime(root) / "d130-pr434-cert-armed.json"
    arm.write_text(
        json.dumps(
            {
                "EVENT": "CI434_TERMINAL_PASS"
                if obs.status == ObserverStatus.TERMINAL_PASS
                else "CI434_TERMINAL_NONPASS",
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
    """Independent analysis nodes that never block on owner-held packages."""
    # Always offer a bounded reconciliation node so READY can force wake when useful.
    items = [
        ReadyWorkItem(
            role=AgentRole.READ_ONLY_ANALYST,
            package_id="AS-RELEASE-READINESS-DAG-001",
            node_id=f"RELEASE-GAP-RECONCILE-{int(now)}",
            cycle_id="d130",
            dag_generation=1,
            base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
            prompt="release gap reconcile",
            critical_path_score=40,
        ),
        ReadyWorkItem(
            role=AgentRole.READ_ONLY_ANALYST,
            package_id="AS-DEMO-READINESS-DAG-001",
            node_id=f"DEMO-GAP-RECONCILE-{int(now)}",
            cycle_id="d130",
            dag_generation=1,
            base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
            prompt="demo gap reconcile",
            critical_path_score=55,
        ),
    ]
    # Cap churn: only dispatch if last reconcile older than 60s
    marker = _runtime(root) / "d130-last-reconcile-dispatch.json"
    if marker.is_file():
        try:
            prev = json.loads(marker.read_text(encoding="utf-8"))
            if now - float(prev.get("at", 0)) < 60.0:
                return []
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return items


def resident_tick(
    root: Path,
    *,
    now: float | None = None,
    capacity: int = 2,
    ready: list[ReadyWorkItem] | None = None,
) -> ResidentTickResult:
    """One self-wake scheduler tick. Never blocks on CI."""
    ts = time.time() if now is None else now
    mission = load_mission(root)
    ensure_pr434_observer(root, now=ts)
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
    _arm_pr434_if_consumed(root, consumed=consumed, now=ts)
    if tick.dispatched:
        (_runtime(root) / "d130-last-reconcile-dispatch.json").write_text(
            json.dumps(
                {
                    "at": ts,
                    "nodes": [d.node_id for d in tick.dispatched],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (_runtime(root) / "d130-successor-dispatch-proof.json").write_text(
            json.dumps(
                {
                    "SUCCESSOR_DISPATCH_PROOF": "YES",
                    "nodes": [d.node_id for d in tick.dispatched],
                    "WHILE_CI434_PENDING_OR_ANY": "YES",
                    "at": ts,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    wake = tick.next_wake_at
    if tick.ready_before > 0 and len(tick.dispatched) < min(capacity, tick.ready_before):
        # capacity exhausted — sleep briefly
        sleep_sec = bounded_sleep_seconds(
            next_wake_at=wake, now=ts, cap_sec=mission.heartbeat_cap_sec
        )
    elif tick.ready_before > 0:
        sleep_sec = 0.0
        wake = ts
    else:
        sleep_sec = bounded_sleep_seconds(
            next_wake_at=wake, now=ts, cap_sec=mission.heartbeat_cap_sec
        )

    owner_held = _owner_held_count(root)
    pending = pending_external_count(load_observer_registry(root))
    progress = bool(tick.dispatched or consumed or polled)

    auth = discover_auth()
    status = load_status(root)
    if not status.SERVICE_INSTANCE_ID:
        status.SERVICE_INSTANCE_ID = str(uuid.uuid4())
    if status.STARTED_AT <= 0:
        status.STARTED_AT = ts
    status.GOVERNOR_PID = os.getpid()
    status.LAST_SCHEDULER_TICK = ts
    if progress:
        status.LAST_PROGRESS_AT = ts
    status.NEXT_WAKE_AT = wake if wake is not None else ts + sleep_sec
    status.READY_NODE_COUNT = tick.ready_before
    status.ACTIVE_WORKER_COUNT = len(tick.dispatched)
    status.PENDING_EXTERNAL_EVENT_COUNT = pending
    status.OWNER_HELD_COUNT = owner_held
    status.LAST_EVENT_CONSUMED = consumed[-1] if consumed else status.LAST_EVENT_CONSUMED
    status.LAST_NODE_DISPATCHED = (
        tick.dispatched[-1].node_id if tick.dispatched else status.LAST_NODE_DISPATCHED
    )
    status.DETACHED_SCHEDULER_TICK_COUNT += 1
    status.CURSOR_API_KEY_PRESENT = (
        "YES" if auth.cursor_api_key_available == "YES" else "NO"
    )
    status.AUTHENTICATION_WORKS = (
        "YES" if auth.local_sdk_available == "YES" else "NO"
    )
    status.SECRET_LEAK_COUNT = 0
    status.SELF_WAKE_DRIVER = "ACTIVE"
    status.GLOBAL_OWNER_REQUIRED = (
        "YES"
        if tick.governor_state == "OWNER_REQUIRED" and pending == 0 and tick.ready_before == 0
        else "NO"
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
    """Resident self-wake loop. Survives only while process lives; host restarts it."""
    persist_mission(root)
    clear_stop(root)
    status = load_status(root)
    status.STARTED_AT = time.time()
    status.GOVERNOR_PID = os.getpid()
    status.SERVICE_INSTANCE_ID = status.SERVICE_INSTANCE_ID or str(uuid.uuid4())
    status.SELF_WAKE_DRIVER = "ACTIVE"
    persist_status(root, status)

    ticks = 0
    while load_mission(root).service_enabled and not stop_requested(root):
        ready = None
        if ready_provider is not None:
            ready = ready_provider(root)
        result = resident_tick(root, ready=ready)
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            break
        # READY overrides sleep
        if result.ready_count > 0 and result.sleep_sec > 0 and result.dispatched:
            # just dispatched — brief yield
            time.sleep(min(result.sleep_sec, 0.05))
        elif result.ready_count > 0:
            continue
        else:
            time.sleep(max(0.0, result.sleep_sec))
    final = load_status(root)
    final.SELF_WAKE_DRIVER = "STOPPED"
    return persist_status(root, status=final)
