# D-205 — ORCH001E-011: governor/loop rehydration across real process restarts

## Origin

Promoted to the active critical-path implementation node by directive
`D-ORCH001E-011-CRITICAL-PATH-WORKSTEAL`, superseding the "documentation
correction, not implemented here" scoping of D-204 (on PR #636's branch,
not yet merged at the time this record was written). D-204's own
"Recommended path" section sketched two candidate approaches without
choosing between them; this record chooses and implements one, and adds
a second layer D-204 did not consider.

## Finding (restated, see D-204 for the full original writeup)

`run_governor_loop_tick()` (`cli.py`) constructed a brand-new, empty
`AutonomousGovernor` on every CLI invocation. Only the loop's own
`LoopState` survived a process restart; the governor's in-memory node
list did not. Any node lookup performed by `AutonomousLoop`
(`_dispatch_leased()`, `apply_observed_result()` — both do
`next(item for item in self._governor.snapshot().nodes if
item.package_id == package_id)` with no default) raised an uncaught
`StopIteration` for any `LoopState` reflecting in-flight work.

A second, related gap D-204 did not name explicitly: `AutonomousGovernor
.__init__` already accepts `lease_projection_store`, and `lease()`
already calls `project_grant(...)` when one is supplied — but
`run_governor_loop_tick()` never supplied one, so the durable lease
projection (`AS-ORCH-DURABLE-LEASE-PROJECTION-001`,
`.atlas/orchestration/autonomy/leases.json`) was never actually being
written to by the real CLI path, even though the mechanism to read it
back already existed and was fully tested in isolation
(`test_as_orch_durable_lease_projection_001.py`).

## Fix

New module `src/project_atlas/orchestration/autonomy/rehydration.py`,
`rehydrate_governor()`. Wired into `run_governor_loop_tick()` (`cli.py`):
the governor is now constructed with a real `lease_projection_store`
(`root / lease_projection.RELATIVE_DEFAULT`), and `rehydrate_governor()`
runs immediately after construction, before `AutonomousLoop` is built or
`tick()`/`recover()` is ever called.

Deliberately reuses existing durable artifacts rather than inventing a
second, competing persisted-DAG model, per the directive:

- **Origination** (any process, including the very first tick on a
  root): runs the existing `discover()` + `ingest_discovery()` pass —
  unconditionally, harmlessly, and identically to what a long-lived
  in-process governor already does today for a fresh node. This alone
  is what would let a future eligible candidate be picked up on a fresh
  process; today it is a no-op because every current `discover()`
  candidate is `eligible=False` (unrelated, out of scope here).
- **LEASED-phase recovery**: cross-checks the persisted `LoopState`
  (`active_package_id`, `active_lease_id`) against the durable lease
  projection. The projection row's `base_pin` must match the live
  `origin/main` (else `STALE_LEASE` — main moved since the lease was
  granted); its `package_id` must match the loop-persisted one (else
  `FOREIGN_PACKAGE`); the row itself must exist and be `ACTIVE` (else
  `LEASE_NOT_PROJECTED`). A full `AgentLease` is then losslessly
  reconstructed from the row (`expected_output` and
  `expiry_or_terminal_condition` are always the same two constants —
  see `leases.py::grant_lease`, the sole place an `AgentLease` is ever
  minted — everything else is a direct field copy). The node itself is
  rebuilt via the governor's own deterministic pilot-node factory and
  walked through the real transition machinery (`add_node` →
  `mark_ready` → the new `AutonomousGovernor.restore_lease()`, which
  appends the reconstructed lease and transitions the node to `LEASED`
  exactly as the original `lease()` call would have, without
  re-consulting or re-granting any owner gate — the gate was already
  correctly enforced once, at the original `lease()` call).
- **Any node other than `PILOT_PACKAGE_ID`**: fails closed
  (`NODE_NOT_REHYDRATABLE`). The governor has exactly one deterministic
  node factory today; any other package's full `WorkNode` definition
  (mutation surface, acceptance criteria, IV requirements) was never
  durably persisted anywhere a rehydration pass could honestly rebuild
  it from. Guessing was rejected in favor of failing closed — this is
  the "fail closed on unknown node/package" safety property the
  directive requires, not a gap.
- **DISPATCHING / AWAITING_RESULT / VALIDATING**: fails closed
  (`EXECUTION_STATE_NOT_REHYDRATABLE`) before touching the governor at
  all. Execution may already be in flight with no durable record of
  exactly how far it got; reconstructing a node here would mean
  guessing at reality rather than reading it from evidence.

### A note on ACTIVE, honestly stated

`NodeState.ACTIVE` (set inside `execute_leased()`) is never itself
persisted anywhere. A crash between a prior process reaching `ACTIVE` in
memory and that process finishing `apply_observed_result()` is
indistinguishable, on disk, from a crash immediately after `lease()`
granted — both leave `LoopState.phase == LEASED`. Rehydration therefore
always reconstructs to `LEASED`, never `ACTIVE`, regardless of which of
those two crash points actually occurred. This is safe specifically
*because* `execute_leased()` has no external side effects for the
in-process pilot host (it only builds an evidence-bundle payload) — the
already-merged PR #637 fix's `LEASED` branch re-runs it once more, which
is idempotent here. This module does not claim to distinguish those two
crash points; it does not need to, for this specific execution host.
A future `ExecutionHostClass` with real external side effects inside
`execute_leased()`-equivalent code would need its own durable
progress record before this same approach could safely extend to it —
noted here, not solved here (no such host class exists on this tree).

### `_complete_validated()` dangling `active_dispatch_id` (found, out of scope)

While tracing every phase's node-lookup exposure, a second, unrelated
defect was found in `loop.py::_complete_validated()`: if a crash occurs
between `apply_observed_result()` persisting `phase=VALIDATING` and its
final `_save(...)` clearing `active_dispatch_id`, a resumed process's
`_complete_validated()` sees `active_dispatch_id is not None` and
silently no-ops forever (`return self._result()`), with the loop
permanently stuck in `VALIDATING` — never crashing, never failing
closed, never progressing. This does not go through
`governor.snapshot().nodes` at all (so `rehydrate_governor()` correctly
still fails closed for `VALIDATING` as a defense-in-depth matter, but
does not by itself cause or fix this specific stuck-loop symptom).
Deliberately **not fixed here**: the correct terminal behavior (fail
closed with a new code? retry `apply_observed_result` from the
persisted evidence, if any exists? something else?) is a real semantic
decision beyond "smaller established-contract defect", and folding it
into this already-large rehydration PR would widen scope the directive
explicitly warns against ("Do not widen semantics unnecessarily").
Recorded in `docs/backlog.md` as a new, separate, unchecked item.

## Reproduction / authentic recovery test

Per the directive's explicit requirement ("Tests must include REAL
SEPARATE PROCESS INVOCATIONS, not merely two objects in one Python
process"):

`tests/unit/test_orchestration_autonomy_rehydration.py::
test_real_subprocess_recovers_leased_pilot_node_after_crash` spawns two
genuinely separate `python -c ...` OS subprocesses against a real,
self-contained git repository (`git init` + a real commit +
`git update-ref refs/remotes/origin/main <sha>`, so `collect_live_inventory`'s
real `git rev-parse origin/main` subprocess call resolves without a
network remote). Process 1 leases the pilot node via the real governor
API, durably projects the lease, and persists `LoopState` at `LEASED` —
then exits without ever calling `tick()`/dispatch, simulating a genuine
crash at that exact point. Process 2 is a fresh `python -c` invocation
of the real `run_governor_loop_tick()` CLI entrypoint, sharing nothing
with process 1 but the filesystem. Before this fix, process 2 would
raise an uncaught `StopIteration` (non-zero exit, traceback on stderr,
no JSON payload at all); the test asserts a clean JSON payload,
`exit_code == 0`, and `phase != "FAILED_CLOSED"`.

The remaining tests in that file exercise `rehydrate_governor()`
directly against a FRESH `AutonomousGovernor` reading only from disk
(never the object that produced the state) — the adversarial matrix:
no prior state (clean origination), all three in-flight execution
phases (fail closed), an unknown package_id (fail closed), a lease_id
with no durable projection row (fail closed), a foreign-package
projection mismatch (fail closed), a stale base_pin after main moved
(fail closed), and `AutonomousGovernor.restore_lease()`'s own contract
that it neither re-invokes nor bypasses an owner gate. These are
honestly framed in the file's own docstring as disk-mediated,
same-process contract tests, not re-claimed as the cross-process proof
— that claim is reserved for the one real-subprocess test above.

## Verification pipeline run so far

- Focused new tests: `tests/unit/test_orchestration_autonomy_rehydration.py`
  — 11 passed (real-subprocess test + 10 disk-mediated adversarial
  tests).
- Full `orchestration or autonomy` suite: 315 passed (301 pre-existing +
  14 new, including the parametrized in-flight-phase matrix), 0
  regressions.
- `ruff check` on all touched files: clean.
- `mypy src`: 0 new errors (2 pre-existing, unrelated errors in
  `connect_perf.py` — a Windows `os.getrusage` platform-stub gap, not
  touched by this change).
- Full repository test suite: run and its result recorded separately
  (see WORKLOG) — not yet independently verified.

## What this does NOT change

- Owner gates A–F are unaffected. `restore_lease()` does not accept an
  `owner_grant` parameter at all — there is no way to pass one — and
  does not re-invoke `require_owner`; it only restores bookkeeping for a
  lease whose gate was already correctly enforced once, at the original
  `lease()` call. `LOOP_CAN_BYPASS_OWNER_GATE = NO` still holds after
  rehydration, verified by
  `test_restore_lease_does_not_reinvoke_or_bypass_owner_gate`.
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`, `MERGE_AUTHORIZATION =
  NOT_GRANTED` — unaffected, this module never calls `request_merge` or
  any owner-gate request method.
- Does not make any `discover()` candidate eligible that wasn't before —
  that is a separate, unrelated, out-of-scope product decision.

## Certification state

**Not self-certified.** This record documents implementation and
first-party test evidence only. Per standing project rule, an
independent verifier (not this implementer) and fresh exact-head CI are
both still required before this is merge-eligible.
`GOVERNED_AUTONOMY_ACTIVE` stays `PARTIAL` until then.
