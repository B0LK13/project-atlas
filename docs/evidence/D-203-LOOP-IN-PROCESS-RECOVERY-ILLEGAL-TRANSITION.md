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

## Certification state

Not self-certified. Independent adversarial IV + exact-head CI required
before certification, per `GOVERNANCE.md`.
