# D-204 — governor-loop-tick CLI: no node rehydration across process restarts (correction)

## Origin

Found by the independent verifier of PR #637 (the `IllegalTransitionError`
recovery fix), who adversarially probed whether the fix "survives a real
process restart" rather than only the in-memory scenario the shipped
tests (and the fix's own new regression test) exercise. Independently
reproduced directly, not taken on trust — see reproduction below.

## Finding

`src/project_atlas/orchestration/autonomy/cli.py`'s
`run_governor_loop_tick()` — the function behind the real CLI command
`atlas orchestrator governor-loop-tick` — constructs a **brand-new,
empty** `AutonomousGovernor` on every invocation:

```python
governor = AutonomousGovernor(
    current_main=inventory.current_main,
    current_tree=inventory.current_tree,
    trusted_anchor=trusted,
)
```

There is no `discover()`/`ingest_discovery()`/`add_node()` call anywhere
in this function before `loop.tick()` runs. Only the loop's own
`LoopState` (phase, `active_package_id`, `active_lease_id`, etc.) is
reloaded from disk — the governor's in-memory node list is always empty
on a fresh process.

This means, for a genuine two-process scenario (process 1 leases/starts
work and is later killed or exits; process 2 is a fresh CLI invocation
against the same `--loop-store`):

- If persisted `phase == IDLE`: harmless — `tick()` correctly finds no
  eligible work and stops cleanly.
- If persisted `phase` is anything else (`LEASED`, `DISPATCHING`,
  `AWAITING_RESULT`, `VALIDATING`) — i.e. **any interrupted-work
  scenario, which is the entire reason a persistent/recoverable loop
  exists** — `recover()`'s governor node lookups
  (`next(item for item in self._governor.snapshot().nodes if
  item.package_id == package_id)`) find nothing and raise an uncaught
  `StopIteration`.

**This is broader than any single recovery-path bug.** It is not fixed
by PR #635 (P3 orphaned-dispatch fix) or PR #637 (this
`IllegalTransitionError` fix) individually, because both operate on the
assumption that the node the loop is tracking still exists in the
governor's snapshot — which is true for every existing test (all of
which keep one `AutonomousGovernor`/`AutonomousLoop` pair alive across
multiple in-process `.tick()` calls, exactly matching
`run_controlled_pilot()`'s and the pilot CLI command's own usage
pattern) but false for the real `governor-loop-tick` CLI entry point
used across separate process invocations.

Deeper still: `run_governor_loop_tick()` never calls `discover()` at
all, so it cannot *originate* new work either — not just recovery, but
the entire "select READY work and start it" path is unreachable via
this CLI command today. `governor-loop-tick` as currently wired is only
meaningfully usable within a single long-lived Python process that
manages its own governor lifecycle (matching exactly how
`AS-ORCH-AUTONOMY-001`'s own pilot flow and every unit test use it) —
not as a repeatable, stateless CLI invocation, which is the premise the
package name "persistent loop" and `docs/backlog.md`'s
`PERSISTENT_AUTONOMOUS_LOOP = IMPLEMENTED` / `AUTONOMOUS_LOOP_001E =
IMPLEMENTED` markers assume.

## Reproduction (independently confirmed, not the IV's script)

Two-"process" simulation using the real governor/loop API — process 1
populates a governor, leases a node, persists `LEASED` state, then
"crashes"; process 2 constructs a fresh empty governor pointed at the
same on-disk store (exactly `run_governor_loop_tick()`'s own
construction) and calls `recover()`:

```
Process 1 (pre-crash) persisted loop state: LEASED LEASE-1
Process 2 (post-restart) governor node count: 0
Process 2 loaded persisted state: LEASED LEASE-1
Calling loop2.recover() -- exactly what governor-loop-tick would do...
REPRODUCED: StopIteration escaped recover() uncaught:
```

## Impact on prior claims (correction, not retraction)

- **D-202 (orchestration activation record)** claimed
  `GOVERNED_ORCHESTRATION_STACK = ACTIVE` / `GOVERNED_AUTONOMY_ACTIVE =
  YES`, grounded in: A-F owner-gate enforcement being live at the real
  selection/lease boundary (still true, independently re-confirmed,
  unaffected by this finding), and the orchestration/autonomy test
  suite passing (still true). It did **not** verify, and should have
  explicitly caveated, whether the real CLI entry point
  (`governor-loop-tick`) can actually originate or recover work across
  separate process invocations — it cannot, per this finding. Amended in
  the same PR (#636) before merge to add this caveat explicitly, rather
  than issuing a silent correction after the fact.
- **PR #635** (P3 orphaned-dispatch fix) and **PR #637** (this
  `IllegalTransitionError` fix): both fixes are still correct and valid
  *within their tested, documented scope* — the in-memory
  governor+loop-reuse pattern every existing caller and test actually
  uses. Neither PR's own claims need reverting, but neither should be
  read as making `governor-loop-tick` safe for real cross-process
  recovery, because a lower-level gap (no node rehydration at all)
  means recovery never reaches either fix's code in that scenario — it
  fails earlier, on the governor snapshot lookup itself.

## What this does NOT change

- A-F owner-gate enforcement at the selection/lease boundary
  (`continuation.py`, `governor.py::lease()`) is unaffected — that
  logic doesn't depend on which nodes happen to be populated; it
  correctly excludes owner-gated nodes whenever they ARE present,
  regardless of how they got there.
- `LOOP_CAN_BYPASS_OWNER_GATE = NO` remains true.
- No production code touched here — this is a documentation correction
  plus a new, explicit backlog item for the real fix.

## Recommended path (not implemented here — scoped for its own work)

Implementing real node rehydration is a genuine design decision, not a
narrow patch: the persisted `LoopState` today carries only
`active_package_id`/`active_lease_id`, not enough to reconstruct a full
`WorkNode` (mutation surface, acceptance criteria, execution host
class, owner gate, etc.). Candidate approaches, not evaluated in depth
here: (a) `run_governor_loop_tick()` calls `discover()` +
`ingest_discovery()` before `tick()`, on the theory that the "pilot"
node (or any future node) is fully deterministic given
`LiveInventory` alone and requires no separate persistence; (b)
persist enough of `WorkNode` in the loop store itself to rehydrate it
directly, bypassing `discover()` on resume. Deliberately not chosen or
implemented here — this is exactly the kind of new-semantics decision
that needs its own dedicated pass, not one folded into an unrelated
crash-recovery bugfix.

## Certification state

This is a documentation-only correction (D-202 caveat) plus a new
backlog item recording the gap; no source code changed by this record.
Not self-certified in the sense of "this problem is solved" — it
explicitly is not; it is honestly recorded as open.
