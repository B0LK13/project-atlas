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

from project_atlas.orchestration.sdk import os_lock
from project_atlas.orchestration.sdk.auth import discover_auth
from project_atlas.orchestration.sdk.closed_loop_port import (
    ensure_closed_loop_binding,
    get_closed_loop_hook,
    persist_governor_mode,
)
from project_atlas.orchestration.sdk.external_observers import (
    ObserverStatus,
    due_observers,
    load_observer_registry,
    pending_external_count,
)
from project_atlas.orchestration.sdk.host import no_window_creationflags
from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE
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
RECEIPT_NAME: Final[str] = "resident-primary-receipt.json"
RECONCILE_INTERVAL_SEC: Final[float] = 45.0

# `read_primary_lock_pid()` returns a positive int for "a live process holds
# the lock" (callers treat `> 0` as live). When the lock IS held (proven by
# a real OS-lock probe) but the JSON receipt alongside it cannot be parsed
# for a PID -- deliberately not hardened further here, see issue #767 -- this
# sentinel is returned instead of fabricating a plausible-looking real PID or
# incorrectly reporting 0 ("no live holder"), which would let a caller start
# a second governor while one is genuinely still running.
MALFORMED_RECEIPT_LIVE_SENTINEL_PID: Final[int] = 2**31 - 1

# Real OS-level lock fds this process currently holds, keyed by resolved
# lock-file path. Populated by `acquire_primary_lock()`, emptied by
# `release_primary_lock()`. This is what makes a second `acquire_primary_lock`
# call from the SAME process idempotent-True without re-locking: the process
# already holds the lease, so there is nothing further to atomically decide.
_HELD_LOCK_FDS: dict[str, int] = {}


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


def _lock_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def acquire_primary_lock(root: Path) -> bool:
    """Ensure ACTIVE_PRIMARY_GOVERNOR_COUNT <= 1 -- as a real cross-process
    invariant, not a best-effort filesystem convention.

    Exclusivity is enforced by a kernel-arbitrated OS lock (`os_lock`), not
    by this process reading then writing a file: two processes racing this
    call can never both receive True, because the OS makes that decision
    atomically in a single call, with no time-of-check-to-time-of-use
    window. Returns True if this process now holds the lease (and either
    just acquired it, or already held it -- a second call from the SAME
    process while it still holds the lease is idempotent-True and does not
    re-lock). Returns False if another live process holds it. Never blocks:
    a single non-blocking attempt, not a wait.

    Crash recovery is automatic and immediate: if the previous holder
    exited (including a crash) without calling `release_primary_lock()`,
    the OS already released its lock when the process's file descriptors
    closed, so the very next attempt here simply succeeds -- no stale-lock
    detection, timeout, or reclamation protocol is needed, and so no new
    race is introduced by one.

    The JSON receipt is a SEPARATE, plain (never locked) file -- see
    `RECEIPT_NAME` -- written only for `read_primary_lock_pid()`'s
    observability. It deliberately never shares a file with the lock
    itself: on Windows, `msvcrt.locking()` is a *mandatory* byte-range
    lock -- any I/O touching the locked bytes, even a plain read from this
    same process, would be denied while the lock is held, not merely
    advisory the way POSIX `flock()` is. Keeping the receipt in its own
    file is what lets it stay freely readable while the lock is held, and
    is never consulted here to decide ownership -- that would reintroduce
    exactly the race this function exists to close.
    """
    path = _runtime(root) / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    key = _lock_key(path)
    if key in _HELD_LOCK_FDS:
        return True  # same-process reacquisition: idempotent, no re-lock

    fd = os_lock.try_acquire_exclusive(path)
    if fd is None:
        return False

    _HELD_LOCK_FDS[key] = fd
    _publish_receipt(root, pid=os.getpid())
    return True


def _publish_receipt(root: Path, *, pid: int) -> None:
    """Safe publication of the informational receipt: write to a sibling
    temp file, flush, then atomically replace -- never a partial/torn read
    for anything that happens to read it mid-write. This is
    RECEIPT_ATOMICITY, deliberately independent from LOCK_ATOMICITY (the OS
    lock itself, which is what actually enforces exclusivity)."""
    receipt_path = _runtime(root) / RECEIPT_NAME
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({"pid": pid, "at": time.time()}, indent=2) + "\n"
    tmp_path = receipt_path.with_name(f".{receipt_path.name}.{pid}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, receipt_path)
    except OSError:
        # Exclusivity is already ours (the OS lock is held); a failure to
        # publish the informational receipt does not change that.
        tmp_path.unlink(missing_ok=True)


def read_primary_lock_pid(root: Path) -> int:
    """Return the live primary lock holder's PID, or 0 if no live holder.

    Liveness is determined by a real, non-blocking OS-lock probe
    (`os_lock.probe_is_locked`) -- never by trusting the receipt file's
    mere existence or its PID field, both of which are racy across
    processes and, on their own, cannot prove exclusivity (this is the
    exact class of bug this mission closes: see issue #773). A crashed
    holder's lock is released by the OS itself, so a stale receipt left
    behind by a crash correctly reads back as "no live holder" (0) here.

    The returned PID is read from the receipt for observability only, not
    to decide liveness. If the receipt cannot be parsed while the lock IS
    genuinely held, this returns `MALFORMED_RECEIPT_LIVE_SENTINEL_PID`
    rather than 0 -- reporting 0 here would tell a caller "no live holder"
    while one is in fact still running, and a watchdog could then start a
    duplicate governor. Hardening the receipt parser itself is tracked
    separately (issue #767) and intentionally out of scope here.
    """
    lock_path = _runtime(root) / LOCK_NAME
    if not os_lock.probe_is_locked(lock_path):
        return 0
    receipt_path = _runtime(root) / RECEIPT_NAME
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        other = int(data.get("pid", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return MALFORMED_RECEIPT_LIVE_SENTINEL_PID
    return other if other > 0 else MALFORMED_RECEIPT_LIVE_SENTINEL_PID


def release_primary_lock(root: Path) -> None:
    """Release the lease this process holds for `root`, if any. Safe to
    call even if this process never held it, or already released it
    (idempotent no-op either way).

    Does not touch the JSON receipt file -- it is left in place as
    historical evidence of the last holder. A future acquirer overwrites
    it only after it has already won the OS lock, never before, so a
    stale receipt can never be mistaken for proof of ownership."""
    path = _runtime(root) / LOCK_NAME
    key = _lock_key(path)
    fd = _HELD_LOCK_FDS.pop(key, None)
    if fd is not None:
        os_lock.release(fd)


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
        creationflags=no_window_creationflags(),
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
        gate_state: dict[str, object] = {"MERGE_AUTHORIZATION": "NOT_GRANTED"}
        try:
            from project_atlas.orchestration.sdk.ci_observer import observe_exact_head_ci
            from project_atlas.orchestration.sdk.merge_sequence_gate import (
                gate_state_path,
                refresh_dependent_merge_gate_state,
            )

            if obs.expected_head and obs.expected_tree:
                ci_obs = observe_exact_head_ci(head_sha=obs.expected_head)
                decision = refresh_dependent_merge_gate_state(
                    root,
                    child_pr_number=436,
                    child_merge_authorized=False,
                    parent_merged=True,
                    parent_merge_commit=obs.expected_head,
                    live_main_sha=obs.expected_head,
                    live_tree_sha=obs.expected_tree,
                    ci_observation=ci_obs,
                )
                gate_state = {
                    "DEPENDENT_MERGE_ALLOWED": decision.allowed,
                    "DEPENDENT_MERGE_REASON": decision.reason,
                    "GATE_STATE_PATH": str(gate_state_path(root)),
                    "MERGE_AUTHORIZATION": "NOT_GRANTED",
                }
        except Exception:
            pass
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
                    **gate_state,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def _dispatch_count(loop_result: dict[str, object] | None) -> int:
    if loop_result is None:
        return 0
    raw = loop_result.get("REAL_WORKER_DISPATCH_COUNT", 0)
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return 0


def _try_closed_loop(root: Path, *, now: float) -> dict[str, object] | None:
    """Invoke registered closed-loop hook; never statically import PR436."""
    mode = ensure_closed_loop_binding()
    persist_governor_mode(root, mode=mode, now=now)
    hook = get_closed_loop_hook()
    if hook is None:
        if mode == "DEGRADED_MISSION_RECONCILER_UNAVAILABLE":
            return {
                "degraded": True,
                "GOVERNOR_MODE": mode,
                "CLOSED_LOOP_AUTONOMY": "FAIL",
                "REAL_WORKER_DISPATCH_COUNT": 0,
                "at": now,
            }
        # RESIDENT_SCHEDULER_ONLY — self-wake continues without mission autonomy
        return None

    # Mandatory cycle when hook is bound
    hook.reconcile(root, now=now)
    marker = _runtime(root) / "d134-last-closed-loop.json"
    if marker.is_file():
        try:
            prev = json.loads(marker.read_text(encoding="utf-8"))
            if now - float(prev.get("at", 0)) < 20.0:
                progress = hook.progress_state(root)
                return {
                    "paced": True,
                    "MISSION_RECONCILE_PER_PRODUCTIVE_TICK": "YES",
                    "GOVERNOR_MODE": "CLOSED_LOOP_MANDATORY",
                    "REAL_ACTIVE_WORKER_COUNT": hook.active_worker_count(root),
                    "MISSION_PROGRESS_SEQUENCE": progress.get("PROGRESS_SEQUENCE", 0),
                    "MISSION_GENERATION": progress.get("MISSION_GENERATION", 0),
                    "at": now,
                }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    items = hook.ready_work(root, capacity=1)
    if not items:
        hook.reconcile(root, now=now)
        items = hook.ready_work(root, capacity=1)

    if items:
        result = dict(hook.closed_loop_tick(root, now=now))
    else:
        progress = hook.progress_state(root)
        result = {
            "MISSION_GENERATION": progress.get("MISSION_GENERATION", 0),
            "READY_NODE_COUNT": 0,
            "REAL_WORKER_DISPATCH_COUNT": 0,
            "note": "empty_ready_after_full_mission_reconcile",
            "EMPTY_READY_QUEUE_RECONCILIATION_COUNT": progress.get(
                "EMPTY_READY_QUEUE_RECONCILIATION_COUNT", 0
            ),
        }

    progress = hook.progress_state(root)
    result["REAL_ACTIVE_WORKER_COUNT"] = hook.active_worker_count(root)
    result["MISSION_PROGRESS_SEQUENCE"] = progress.get("PROGRESS_SEQUENCE", 0)
    result["MISSION_RECONCILE_PER_PRODUCTIVE_TICK"] = "YES"
    result["GOVERNOR_MODE"] = "CLOSED_LOOP_MANDATORY"
    result["at"] = now
    marker.write_text(json.dumps({"at": now}, indent=2) + "\n", encoding="utf-8")
    return result


def _default_ready(root: Path, *, now: float) -> list[ReadyWorkItem]:
    """READY from closed-loop hook when bound; else empty (no synthetic cards)."""
    ensure_closed_loop_binding()
    hook = get_closed_loop_hook()
    if hook is None:
        return []
    items = hook.ready_work(root, capacity=2)
    if not items:
        hook.reconcile(root, now=now)
        items = hook.ready_work(root, capacity=2)
    return list(items)


def _record_dispatch_progress(root: Path, *, now: float, nodes: list[str]) -> None:
    (_runtime(root) / "d134-last-scheduler-dispatch.json").write_text(
        json.dumps({"at": now, "nodes": nodes, "synthetic": False}, indent=2) + "\n",
        encoding="utf-8",
    )


def resident_tick(
    root: Path,
    *,
    now: float | None = None,
    capacity: int = 3,
    ready: list[ReadyWorkItem] | None = None,
) -> ResidentTickResult:
    """One self-wake scheduler tick. Never blocks on CI."""
    ts = time.time() if now is None else now
    mission = load_mission(root)
    ensure_active_observers(root, now=ts)
    snapshots = _ci_snapshots_for_due(root, now=ts)

    # Closed-loop work producer (when mission reconciler package is present)
    loop_result = _try_closed_loop(root, now=ts)

    work = ready if ready is not None else _default_ready(root, now=ts)
    # If still empty after reconcile, count empty-queue reconciliation
    if not work and loop_result is None:
        (_runtime(root) / "d132-empty-ready-reconcile.json").write_text(
            json.dumps({"at": ts, "note": "empty_ready_no_mission_reconciler"}, indent=2)
            + "\n",
            encoding="utf-8",
        )

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
    sleep_sec = bounded_sleep_seconds(
        next_wake_at=wake, now=ts, cap_sec=mission.heartbeat_cap_sec
    )
    if tick.ready_before > 0:
        sleep_sec = max(0.5, min(sleep_sec, mission.heartbeat_cap_sec))
        wake = ts + sleep_sec

    owner_held = _owner_held_count(root)
    pending = pending_external_count(load_observer_registry(root))
    # PROJECT_PROGRESS only for real closed-loop outcomes or CI consume
    real_progress = bool(consumed) or _dispatch_count(loop_result) > 0 or bool(
        loop_result and loop_result.get("created_successors")
    )

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
    if real_progress:
        status.LAST_PROGRESS_AT = ts
        status.progress_sequence += 1
    status.NEXT_WAKE_AT = wake if wake is not None else ts + sleep_sec
    status.READY_NODE_COUNT = tick.ready_before
    hook = get_closed_loop_hook()
    status.ACTIVE_WORKER_COUNT = hook.active_worker_count(root) if hook else 0
    status.PENDING_EXTERNAL_EVENT_COUNT = pending
    status.OWNER_HELD_COUNT = owner_held
    status.LAST_EVENT_CONSUMED = consumed[-1] if consumed else status.LAST_EVENT_CONSUMED
    if loop_result and loop_result.get("worker_id"):
        status.LAST_NODE_DISPATCHED = str(loop_result.get("worker_id"))
    elif tick.dispatched:
        status.LAST_NODE_DISPATCHED = tick.dispatched[-1].node_id
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
        and loop_result is None
        else "NO"
    )
    status.CASE = classify_runtime_case(
        process_exists=True,
        ticks_advance=True,
        ready_count=tick.ready_before,
        useful_dispatch=real_progress or tick.ready_before == 0,
        watchdog_ok=True,
    )
    persist_status(root, status)

    if loop_result is not None:
        (_runtime(root) / "d132-closed-loop-last.json").write_text(
            json.dumps(loop_result, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

    result = ResidentTickResult(
        tick_at=ts,
        next_wake_at=status.NEXT_WAKE_AT,
        ready_count=tick.ready_before,
        pending_external=pending,
        dispatched=[d.node_id for d in tick.dispatched],
        terminal_consumed=consumed,
        observers_polled=polled,
        progress=real_progress,
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
            "real_progress": real_progress,
            "closed_loop": bool(loop_result),
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
        while True:
            mission = load_mission(root)
            if not mission.service_enabled or stop_requested(root):
                break
            ready = None
            if ready_provider is not None:
                ready = ready_provider(root)
            result = resident_tick(root, ready=ready)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            # READY overrides long sleep, but never busy-spin: floor after dispatch.
            if result.ready_count > 0 and result.dispatched:
                time.sleep(max(0.5, min(result.sleep_sec, mission.heartbeat_cap_sec)))
            elif result.ready_count > 0:
                time.sleep(max(0.2, min(result.sleep_sec, mission.heartbeat_cap_sec)))
            else:
                time.sleep(max(0.0, result.sleep_sec))
    finally:
        release_primary_lock(root)
    final = load_status(root)
    final.SELF_WAKE_DRIVER = "STOPPED"
    final.ACTIVE_PRIMARY_GOVERNOR_COUNT = 0
    return persist_status(root, status=final)
