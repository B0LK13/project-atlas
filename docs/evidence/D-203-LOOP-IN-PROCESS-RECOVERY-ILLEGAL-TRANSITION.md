# D-203 — loop.py IN_PROCESS recovery: IllegalTransitionError escape (pre-existing)

## Origin

Found by the independent verifier of PR #635 (ORCH001E-008 P3 fix), who
confirmed via a control test that this defect is **pre-existing** on the
unmodified `LEASED` recovery branch, not introduced by that PR (though
PR #635's own new not-found retry path also calls into the same
`_dispatch_leased()`, so it's reachable from both). Recorded separately
there rather than folded in, per the owner directive's own instruction
to classify it as its own work-steal node.

## Classification (owner directive's 5 questions)

1. **Exact reachable state transition**: `AutonomousLoop._dispatch_leased()`'s
   `IN_PROCESS` branch called `governor.execute_leased(lease_id)`
   unconditionally. `execute_leased()` calls
   `self.transition(lease.package_id, NodeState.ACTIVE, "IN_PROCESS_EXECUTE")`
   unconditionally too. If a crash happens between `execute_leased()`
   succeeding (node state -> `ACTIVE`) and `apply_observed_result()`
   running (whose *first* action is `_save(phase=VALIDATING)` -- the only
   thing that would move the loop off `LEASED`), the loop's persisted
   state is stuck at `phase=LEASED` with a node that is no longer
   `LEASED`. On restart, `recover()`'s `LEASED` branch re-enters
   `_dispatch_leased()`, which calls `execute_leased()` again -> attempts
   `ACTIVE -> ACTIVE`, illegal per `dag.py`'s `ALLOWED_TRANSITIONS` table
   -> `IllegalTransitionError`.
2. **Externally reachable via the real CLI/autonomous loop**: yes.
   `cli.py`'s `run_governor_loop_tick()` catches only
   `(TrustError, DiscoveryError, LoopError)` -- `IllegalTransitionError`
   is a bare `ValueError` subclass (`dag.py`), not a `LoopError`, so it
   is not caught and escapes the CLI handler as an unstructured crash
   (confirmed by reading the exact `except` tuple, not assumed).
3. **Expected repository-defined fail-closed behavior**: every other
   failure path in this module translates internal errors into a
   `LoopError` with an explicit `code` before it can reach a caller
   (`_fail()`); an uncaught `IllegalTransitionError` breaks that
   convention.
4. **Can it strand persistent autonomy**: yes, and worse than
   "fail-stuck" -- the loop state file is unchanged by an uncaught
   exception, so every subsequent invocation hits the identical crash
   again (a repeating hard failure, not a quiescent stall).
5. **Correct exception translation/recovery boundary**: `_dispatch_leased()`'s
   `IN_PROCESS` branch, since that's exactly where the unconditional
   re-execution attempt happens.

## Reproduction (before fix)

Constructed the precise crash window directly (governor `lease()` call,
then a direct `execute_leased()` call simulating "this part already
succeeded before the crash", then a hand-persisted loop state matching
what `_select_and_lease()` would have saved just before entering
`_dispatch_leased()`), then called `loop.recover()` -- exactly what a
restarted process would do:

```
governor node state after execute_leased(): ACTIVE
loop's own persisted state (unaware): LEASED
Calling loop.recover()...
REPRODUCED: IllegalTransitionError escaped recover() uncaught: illegal transition ACTIVE -> ACTIVE
```

## Fix

`_dispatch_leased()`'s `IN_PROCESS` branch now checks `node.state`
before calling `execute_leased()`:

- `node.state == NodeState.LEASED` (normal, not-yet-executed case):
  call `execute_leased()` as before, now wrapped in a defensive
  `try/except IllegalTransitionError` that fails closed with a new
  `EXECUTION_STATE_CONFLICT` `LoopError` instead of letting a residual
  race escape uncaught.
- `node.state != NodeState.LEASED` (the crash-window case): skip
  `execute_leased()` entirely and go straight to
  `apply_observed_result(in_process_id, in_process_id, passed=True)`.
  This is safe because: (a) `IN_PROCESS` execution is fully synchronous
  with no partial/async state, so its outcome is completely re-derived
  from the same deterministic id (`f"in-process:{lease_id}"`, used as
  both `dispatch_id` and `digest`); (b) `apply_observed_result()` is
  itself replay-guarded (`RESULT_REPLAY`) against being applied twice;
  (c) `apply_observed_result()` already contains its own
  `if node.state is NodeState.LEASED: transition(..., ACTIVE, ...)`
  guard, so calling it on an already-`ACTIVE` node correctly skips the
  redundant transition and proceeds straight to verification/
  certification, exactly reproducing what would have happened had the
  crash not occurred.

**Scope boundary checked explicitly**: could the crash window instead
land with the node already `CERTIFIED` (i.e. `apply_observed_result` had
already run to completion) while the loop still shows `LEASED`? No --
`apply_observed_result()`'s very first action is `_save(phase=
VALIDATING)`, so the instant it starts running, the loop's own phase
moves off `LEASED`. A crash at or after that point leaves
`phase=VALIDATING`, which routes through the pre-existing, unmodified
`_complete_validated()` branch instead -- not the branch this fix
touches. So within the `LEASED`-and-not-yet-`VALIDATING` window, the
node can only be `ACTIVE` (not further along), which is exactly the case
handled.

**Not fixed / not in scope**: the pre-existing `try/except Exception:
pass` pattern used for `expand_lease()` elsewhere in this file, and any
other unconditional governor calls outside `_dispatch_leased()`'s
`IN_PROCESS` branch, were not audited here -- this fix is scoped to the
exact reproduced defect, per "do not widen semantics unnecessarily."

## Validation

- New regression test
  `test_in_process_recovery_after_crash_before_apply_observed_result`:
  reproduces the exact crash window via the governor's real API (not
  mocks), confirms `recover()` no longer raises, and confirms the node
  reaches a terminal governed state (`CERTIFIED`/`OWNER_HELD`/`CLOSED`).
- `pytest tests/unit/test_orchestration_autonomy_loop.py
  tests/unit/test_orchestration_autonomy.py`: 60/60 passed.
- `pytest -k "orchestration or autonomy"`: 299/299 passed, 4312
  deselected.
- `ruff check` / `mypy` on touched files: clean.

## Round 3 (PR #637 review thread `PRRT_kwDOTtguR86dRAuB`, chatgpt-codex-connector, P1)

**Finding**: rounds 1-2 above fixed the *in-memory, same-governor-object*
recovery contract, but `test_in_process_recovery_after_crash_before_apply_observed_result`
reused the same in-memory `AutonomousGovernor` for both the "before crash"
and "recovery" calls, so it never exercised what a real process restart
does. `run_governor_loop_tick()` (`orchestration/autonomy/cli.py`)
constructs a brand-new `AutonomousGovernor` from live inventory alone on
*every* invocation -- its node/lease list starts empty -- while only this
loop's own `LoopState` survives on disk between processes. Any node lookup
in that recovery path (`_dispatch_leased()`'s `IN_PROCESS` branch,
`apply_observed_result()`'s two node lookups) was a bare
``next(item for item in governor.snapshot().nodes if ...)`` with no
default: against a real restart's empty node list this raises an uncaught
`StopIteration`, not a `LoopError` -- `cli.py`'s
``except (TrustError, DiscoveryError, LoopError)`` does not catch it, so it
escapes as an unstructured crash, repeating on every subsequent tick.

**Scope decision**: full governor node/lease rehydration across a real
process restart is its own, larger, separately tracked fix
(`ORCH001E-011`, ORCH001E-011's own PR, developed in parallel) -- it
depends on wiring a durable lease-projection store into
`run_governor_loop_tick()` (not currently passed there at all: the
governor it constructs is built without `lease_projection_store=...`, so
today nothing is even durably recorded for this fix to rehydrate from) and
a node-reconstruction factory. Reimplementing that here would duplicate
and likely conflict with the in-flight sibling PR. Per this repo's
fail-closed convention (`LOOP_CAN_BYPASS_OWNER_GATE = NO`-style hard
guarantees; every other internal error in this module is translated to a
`LoopError` with an explicit `code` before it can reach a caller), the
correct fix *for this PR* is: fail closed with a structured, CLI-catchable
error instead of guessing at a resume path. Chose fail-closed deliberately
rather than attempting partial rehydration, since this PR's own node
factory has no durable definition to rebuild an arbitrary `package_id`
from (only `PILOT_PACKAGE_ID` is deterministically reconstructable, and
only once the lease-projection wiring above exists).

**Fix**: `_dispatch_leased()` and both node lookups inside
`apply_observed_result()` now use
``next((item for item in governor.snapshot().nodes if ...), None)`` and,
when `None`, fail closed via `_fail()` with a new
`GOVERNOR_STATE_NOT_REHYDRATED` `LoopError` code -- distinct from
`EXECUTION_STATE_CONFLICT` (node present but in an unexpected state) since
this is "node absent entirely" (a rehydration gap), a different, more
specific diagnostic for whoever lands `ORCH001E-011` next.

**Test**: added
`test_in_process_recovery_after_real_process_restart_fails_closed`, which
constructs two fully independent `AutonomousGovernor` instances (no shared
Python object) -- the second with zero nodes, exactly mirroring what
`run_governor_loop_tick()` builds on a real invocation -- and points a
second `AutonomousLoop` at the *same on-disk store path* the first one
persisted to, so it only ever learns of the in-flight lease via the
reloaded `LoopState`. Asserts `recover()` raises `LoopError` with code
`GOVERNOR_STATE_NOT_REHYDRATED` (not an uncaught `StopIteration`) and that
the loop phase lands on `FAILED_CLOSED`. The original same-process test is
kept (renamed
`test_in_process_recovery_within_same_process_after_partial_execution`,
docstring updated to state its narrower, still-valid scope) since it
documents a real, different contract: a caller that catches an exception
mid-tick and retries `recover()` without the OS process actually
restarting.

**Validation**: `pytest tests/unit/test_orchestration_autonomy_loop.py`:
25/25 passed. `pytest tests/ -k "loop or governor or recovery or
illegal_transition"`: 131 passed, 2 skipped (Windows-only skips,
pre-existing), 4480 deselected. Full suite, `ruff check .`, `mypy src`:
see PR #637 for the run recorded at the round-3 commit.

## Certification state

Not self-certified. Independent adversarial IV + exact-head CI required
before certification, per `GOVERNANCE.md`.
