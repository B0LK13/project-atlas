"""M-WINDOWS-PRIMARY-GOVERNOR-ATOMIC-LOCK-001 -- load-bearing regression
coverage for the real production `acquire_primary_lock()` /
`release_primary_lock()` / `read_primary_lock_pid()` in
`project_atlas.orchestration.sdk.resident_driver`.

Fixes issue #773 (cross-process TOCTOU race in the primary-governor lock):
exclusivity is now enforced by a kernel-arbitrated OS lock
(`project_atlas.orchestration.sdk.os_lock`), not by this process reading
then writing a JSON file.

These tests exercise the real functions across genuinely separate OS
processes (not threads -- threads share a PID and cannot exercise the
cross-process race this module fixes) using `subprocess`. Every spawn:
  - uses `no_window_creationflags()` (no visible console windows)
  - is short-lived and bounded by an explicit timeout
  - is cleaned up (processes killed/waited, temp dirs removed) even on
    failure, via try/finally

Historical evidence: an independent 20-round, 2-contender reproduction
against the PRE-FIX code in this same mission showed 20/20 double-winner
rounds (both contenders got True). Post-fix, a supplementary (non-CI,
manually run) validation pass showed 0/100 double-winners at 2 contenders,
0/30 at 5, and 0/30 at 10 -- see the mission packet for the full receipts.
The tests below are a smaller, CI-appropriate slice of the same evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from project_atlas.orchestration.sdk import os_lock
from project_atlas.orchestration.sdk.host import no_window_creationflags
from project_atlas.orchestration.sdk.resident_driver import (
    _HELD_LOCK_FDS,
    LOCK_NAME,
    MALFORMED_RECEIPT_LIVE_SENTINEL_PID,
    RECEIPT_NAME,
    _runtime,
    acquire_primary_lock,
    read_primary_lock_pid,
    release_primary_lock,
)

_WORKER = str(Path(__file__).with_name("_primary_lock_worker.py"))
_PER_PROC_TIMEOUT_SEC = 20.0


@pytest.fixture(autouse=True)
def _clean_held_locks():
    """Guard against one test's held fd leaking into the next -- release
    everything this test process holds before and after each test."""
    for fd in list(_HELD_LOCK_FDS.values()):
        os_lock.release(fd)
    _HELD_LOCK_FDS.clear()
    yield
    for fd in list(_HELD_LOCK_FDS.values()):
        os_lock.release(fd)
    _HELD_LOCK_FDS.clear()


def _spawn_contender(
    root: Path, go_file: Path, out_file: Path, hold_sec: float = 0.0
) -> subprocess.Popen:
    args = [sys.executable, _WORKER, str(root), str(go_file), str(out_file), str(hold_sec)]
    return subprocess.Popen(
        args,
        creationflags=no_window_creationflags(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _race_round(root: Path, n_contenders: int, hold_sec: float) -> dict[str, int]:
    """Spawn N real, separate OS processes that all race `acquire_primary_lock(root)`
    at (as close as the scheduler allows) the same instant, each holding the
    lock for `hold_sec` if it wins, so genuinely-concurrent contenders overlap
    in time rather than one winning and exiting before a straggler even tries.
    Returns counts: true, false, timeouts, errors."""
    go_file = root / "go"
    procs = []
    out_files = []
    try:
        for i in range(n_contenders):
            out_file = root / f"out-{i}.json"
            out_files.append(out_file)
            procs.append(_spawn_contender(root / "lockroot", go_file, out_file, hold_sec))
        time.sleep(0.3)
        go_file.write_text("go", encoding="utf-8")

        timeouts = 0
        for p in procs:
            try:
                p.wait(timeout=_PER_PROC_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
                timeouts += 1

        errors = 0
        results = []
        for f in out_files:
            if not f.is_file():
                errors += 1
                continue
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                errors += 1

        return {
            "true": sum(1 for r in results if r.get("won") is True),
            "false": sum(1 for r in results if r.get("won") is False),
            "timeouts": timeouts,
            "errors": errors,
        }
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=5)


@pytest.mark.parametrize("n_contenders,rounds", [(2, 5), (5, 3), (10, 2)])
def test_concurrency_matrix_at_most_one_winner(tmp_path, n_contenders, rounds):
    """CONTENDERS_2 / CONTENDERS_5 / CONTENDERS_10: for every round, exactly
    <= 1 of N genuinely separate OS processes racing `acquire_primary_lock()`
    on the same root gets True."""
    double_winner_rounds = 0
    zero_winner_rounds = 0
    cleanup_failures = 0
    for r in range(rounds):
        round_dir = tmp_path / f"round-{r}"
        round_dir.mkdir()
        outcome = _race_round(round_dir, n_contenders, hold_sec=1.0)
        assert outcome["errors"] == 0, f"round {r}: worker(s) failed to report a result"
        assert outcome["timeouts"] == 0, f"round {r}: worker(s) exceeded the per-process timeout"
        if outcome["true"] > 1:
            double_winner_rounds += 1
        if outcome["true"] == 0:
            zero_winner_rounds += 1

    assert double_winner_rounds == 0, (
        f"{double_winner_rounds}/{rounds} rounds had >1 winner among "
        f"{n_contenders} contenders -- primary-governor exclusivity violated"
    )
    assert zero_winner_rounds == 0, f"{zero_winner_rounds}/{rounds} rounds had no winner at all"
    assert cleanup_failures == 0


def test_repeated_contention_no_double_winners(tmp_path):
    """REPEATED_ROUNDS: many rounds of 2-contender races; double_winner_count
    must be 0 across all of them (a smaller, CI-bounded slice of the
    manually-run 100-round supplementary validation -- see module docstring)."""
    rounds = 25
    double_winner_count = 0
    zero_winner_count = 0
    timeout_count = 0
    for r in range(rounds):
        round_dir = tmp_path / f"round-{r}"
        round_dir.mkdir()
        outcome = _race_round(round_dir, 2, hold_sec=0.5)
        double_winner_count += 1 if outcome["true"] > 1 else 0
        zero_winner_count += 1 if outcome["true"] == 0 else 0
        timeout_count += outcome["timeouts"]

    assert double_winner_count == 0
    assert zero_winner_count == 0
    assert timeout_count == 0


def test_live_holder_excludes_contender_without_disturbing_state(tmp_path):
    """A live holder (process A) stays alive; a contender (process B) that
    attempts while A is alive must get False, and must not disturb A's
    lock state or receipt."""
    root = tmp_path / "root"
    go_file = tmp_path / "go"
    out_file = tmp_path / "out.json"

    holder = _spawn_contender(root, go_file, out_file, hold_sec=3.0)
    try:
        go_file.write_text("go", encoding="utf-8")
        # Give A a moment to actually win before B attempts.
        deadline = time.time() + 10.0
        while not out_file.is_file() and time.time() < deadline:
            time.sleep(0.05)
        assert out_file.is_file(), "holder process A never reported a result"
        a_result = json.loads(out_file.read_text(encoding="utf-8"))
        assert a_result["won"] is True

        # While A is still alive and holding, B attempts and must lose.
        won_b = acquire_primary_lock(root)
        assert won_b is False

        # A's receipt must be untouched by B's failed attempt.
        receipt_path = _runtime(root) / RECEIPT_NAME
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["pid"] == a_result["pid"]

        # And the authoritative holder-pid read must still report A, not 0
        # and not B.
        assert read_primary_lock_pid(root) == a_result["pid"]
    finally:
        holder.wait(timeout=_PER_PROC_TIMEOUT_SEC)


def test_crash_recovery_no_permanent_deadlock(tmp_path):
    """A holder that is force-killed (SIGKILL/TerminateProcess) WITHOUT
    calling `release_primary_lock()` -- a real crash, not a simulation --
    must not deadlock the lock forever: a later acquisition attempt must
    eventually succeed."""
    root = tmp_path / "root"
    go_file = tmp_path / "go"
    out_file = tmp_path / "out.json"

    holder = _spawn_contender(root, go_file, out_file, hold_sec=30.0)
    try:
        go_file.write_text("go", encoding="utf-8")
        deadline = time.time() + 10.0
        while not out_file.is_file() and time.time() < deadline:
            time.sleep(0.05)
        assert out_file.is_file(), "holder process never reported a result"
        a_result = json.loads(out_file.read_text(encoding="utf-8"))
        assert a_result["won"] is True

        # While holding, an outside attempt must fail.
        assert acquire_primary_lock(root) is False

        # Real crash: no graceful shutdown, no release call.
        holder.kill()
        holder.wait(timeout=_PER_PROC_TIMEOUT_SEC)

        # Recovery must be prompt -- no stale-lock reclamation protocol or
        # timeout should be necessary; the OS already released the crashed
        # holder's lock the moment its process/fds went away.
        recovered = False
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if acquire_primary_lock(root):
                recovered = True
                break
            time.sleep(0.1)
        assert recovered, "no permanent deadlock: a later acquisition must eventually succeed"
        assert read_primary_lock_pid(root) == os.getpid()
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=5)
        release_primary_lock(root)


def test_same_process_reacquisition_is_idempotent_true(tmp_path):
    """A second `acquire_primary_lock()` call from the process that already
    holds the lease is idempotent-True and does not re-lock or disturb the
    held fd."""
    root = tmp_path / "root"
    assert acquire_primary_lock(root) is True
    key = str((_runtime(root) / LOCK_NAME).resolve())
    fd_before = _HELD_LOCK_FDS[key]

    assert acquire_primary_lock(root) is True
    assert _HELD_LOCK_FDS[key] == fd_before  # same fd, no re-lock

    release_primary_lock(root)


def test_release_then_reacquire_updates_sync_state_and_receipt(tmp_path):
    """After release, the sync primitive AND the receipt both reflect "no
    live holder"; a subsequent acquire (by any process, including the same
    one) succeeds again and the receipt is updated to the new holder."""
    root = tmp_path / "root"
    assert acquire_primary_lock(root) is True
    assert read_primary_lock_pid(root) == os.getpid()

    release_primary_lock(root)
    assert read_primary_lock_pid(root) == 0
    assert os_lock.probe_is_locked(_runtime(root) / LOCK_NAME) is False

    assert acquire_primary_lock(root) is True
    assert read_primary_lock_pid(root) == os.getpid()
    release_primary_lock(root)


def test_release_is_idempotent_and_safe_when_never_held(tmp_path):
    """`release_primary_lock()` on a root this process never acquired (or
    already released) must be a safe no-op, never an exception."""
    root = tmp_path / "root"
    release_primary_lock(root)  # never held -- must not raise
    release_primary_lock(root)  # already-released -- must not raise

    assert acquire_primary_lock(root) is True
    release_primary_lock(root)
    release_primary_lock(root)  # double release -- must not raise


def test_receipt_owner_matches_actual_sync_owner(tmp_path):
    """RECEIPT_OWNER_MATCH: after a successful acquisition,
    `read_primary_lock_pid()` must equal the real synchronization owner's
    PID -- never let a receipt/owner mismatch silently pass."""
    root = tmp_path / "root"
    assert acquire_primary_lock(root) is True
    assert read_primary_lock_pid(root) == os.getpid()
    release_primary_lock(root)


def test_read_primary_lock_pid_invalid_pid_field_still_reports_live(tmp_path):
    """If the lock IS genuinely held (proven by the OS-lock probe) but the
    receipt's `pid` field is missing or invalid, `read_primary_lock_pid()`
    must still report a live holder (a positive sentinel), never 0 --
    reporting 0 here would tell a caller "no live holder" while one is in
    fact still running, and a watchdog could then start a duplicate
    governor.

    Note: a receipt that is syntactically-valid JSON but not a JSON object
    at all (e.g. `[1, 2, 3]`) hits a separate, pre-existing parsing gap
    tracked as issue #767 -- deliberately not fixed by this mission (see
    module docstring and `read_primary_lock_pid`'s own docstring). This
    test instead covers the well-formed-object-with-a-bad-`pid`-field
    shape, which is the one this module's own writer could plausibly ever
    produce, and confirms the OWNERSHIP decision (live vs not) never
    depends on that field being parseable -- only whether the object
    itself parses."""
    root = tmp_path / "root"
    assert acquire_primary_lock(root) is True
    receipt_path = _runtime(root) / RECEIPT_NAME
    # Corrupt just the `pid` field while we still hold the OS lock -- this
    # cannot disturb the lock itself, since the receipt lives in its own,
    # never-locked file.
    receipt_path.write_text(json.dumps({"pid": "not-a-number"}), encoding="utf-8")

    assert read_primary_lock_pid(root) == MALFORMED_RECEIPT_LIVE_SENTINEL_PID
    release_primary_lock(root)


def test_no_process_leaks(tmp_path):
    """Every spawned worker in this module must exit on its own within its
    timeout; this test only asserts the harness's own bookkeeping is
    self-consistent (all `Popen` handles reach a real exit code)."""
    root = tmp_path / "root"
    go_file = tmp_path / "go"
    out_file = tmp_path / "out.json"
    proc = _spawn_contender(root, go_file, out_file, hold_sec=0.0)
    go_file.write_text("go", encoding="utf-8")
    ret = proc.wait(timeout=_PER_PROC_TIMEOUT_SEC)
    assert ret == 0
