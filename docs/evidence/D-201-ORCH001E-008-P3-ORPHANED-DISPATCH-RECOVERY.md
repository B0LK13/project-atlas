# D-201 — ORCH001E-008 P3: orphaned-dispatch crash-recovery remediation

## Context

WORKLOG's `ORCH001E-008` independent verification (2026-08-28) recorded
three non-blocking follow-ups, one of which (P3) was never remediated:

> a crash between `DispatchPort.dispatch_once()` succeeding and the loop
> persisting `active_dispatch_id` leaves the loop permanently stuck in
> `DISPATCHING` on restart with no path to locate the orphaned dispatch.
> Fail-stuck, not fail-dangerous (no duplicate dispatch) -- an
> operability gap, not a safety one.

## Root cause (confirmed by reading the code, not just the finding)

`AutonomousLoop._dispatch_leased()`:

```python
self._save(phase=LoopPhase.DISPATCHING)
receipt = self._dispatch.dispatch_once(self._root)   # <- crash window
...
self._save(active_dispatch_id=dispatch_id, phase=LoopPhase.AWAITING_RESULT)
```

If the process crashes between the two `_save` calls, the persisted state
is `phase=DISPATCHING, active_dispatch_id=None`. `AutonomousLoop.recover()`
only had branches for `DISPATCHING and active_dispatch_id` (truthy) and
`AWAITING_RESULT` -- neither matches `DISPATCHING` with a falsy
`active_dispatch_id`, so it fell through to a no-op
`return self._result(recovered=True)`. Every subsequent `tick()` routes
`DISPATCHING`/`AWAITING_RESULT` phases straight to `recover()`
(`loop.py` `tick()`), so this state is a permanent stall, not a transient
one.

Separately confirmed the real 001D dispatcher (`dispatcher.py`,
`run_dispatch_once`) calls `persist_active(workspace, dispatch_id,
record.status)` immediately after computing `dispatch_id` and before any
process is spawned -- well before the loop's own crash window closes.
`load_active(root)` reads that same independent record. This is the
correct reconciliation source: the 001D side already knows what it
started; the loop's own state file is just the piece that can lag behind
a crash.

## Remediation

`DispatchPort` (the abstract boundary the loop uses -- `loop.py` never
imports the concrete `dispatcher.py` module, by design) gains one new
method:

```python
def find_active_dispatch_id(self, root: Path) -> str | None:
    """Best-effort discovery ... Returns None when no 001D-side record
    exists (or the port cannot determine one) -- never invents an
    identity."""
```

`AutonomousLoop.recover()` gets a new branch for
`phase == DISPATCHING and not active_dispatch_id`:

- Ask the port via `find_active_dispatch_id(root)`.
- If it returns an id: reject if already in `completed_dispatch_ids`
  (replay guard, matching the existing pattern), otherwise persist it as
  `active_dispatch_id` and proceed through the same reconciliation path
  the existing branch already uses (`self._dispatch.recover(...)`,
  handling COMPLETED/FAILED/still-running identically).
- If it returns `None`: nothing is known to have started, so it's safe
  to reset to `LEASED` and retry via the existing `_dispatch_leased()`
  path -- no process identity exists that a retry could duplicate.

`CallableDispatchPort` (the test/CLI adapter) gets a matching optional
`find_active_dispatch_id` callable, defaulting to `None` (i.e. "no
record"), consistent with its existing `recover` parameter's default
pattern.

**Explicitly out of scope for this commit:** there is currently no
concrete production `DispatchPort` implementation anywhere in the
codebase wiring `dispatch_once`/`recover` to the real
`dispatcher.run_dispatch_once`/`recover_dispatch` (confirmed by
grep -- `AutonomousLoop` is only ever exercised with `CallableDispatchPort`
fakes in tests today; ORCH001E itself is `NOT MERGED`, per
`docs/backlog.md`). This commit fixes the abstract protocol-level gap and
proves it with the same fake-port pattern every other loop test already
uses. A real adapter wiring `find_active_dispatch_id` to
`dispatcher.load_active` is a separate, currently-nonexistent piece of
work -- noted here so it isn't silently assumed done.

## Validation (this session, exact worktree head, base `origin/main` 2cc3c82a)

New regression tests (none of this crash-window behavior was previously
exercised by any existing test):

- `test_orphaned_dispatch_recovery_reconciles_completed` -- port finds the
  orphaned id, reports it COMPLETED; loop applies the result normally and
  never re-dispatches (`calls == ["dispatch"]`, not two).
- `test_orphaned_dispatch_recovery_reconciles_still_running` -- port finds
  the orphaned id, still running; loop's `active_dispatch_id` is restored
  and phase becomes `AWAITING_RESULT` (identity recovered, not lost).
- `test_orphaned_dispatch_recovery_finds_nothing_retries_cleanly` -- port
  genuinely has no record; loop resets to `LEASED` and retries exactly
  once (`calls == ["dispatch", "dispatch"]` -- the original attempt plus
  one clean retry, not a hang and not a duplicate-on-top-of-a-real-process).

Results:

- `pytest tests/unit/test_orchestration_autonomy_loop.py
  tests/unit/test_orchestration_autonomy.py`: 46/46 passed.
- `pytest -k "orchestration or autonomy"`: 285/285 passed, 4287
  deselected.
- `ruff check` (touched files): clean.
- `mypy loop.py`: clean.

## Certification state

Not self-certified. This branch is independent of, and based on `main`
without, the still-unmerged ORCHAUT-010 fix (PR #633) -- different part
of `loop.py`, no textual overlap, but will need a routine
rebase/merge once #633 lands. Independent adversarial IV + exact-head CI
required before certification, per `GOVERNANCE.md`.
