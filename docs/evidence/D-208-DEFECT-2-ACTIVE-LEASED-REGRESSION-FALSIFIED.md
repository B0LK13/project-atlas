# D-208 — Defect 2 (`ACTIVE -> LEASED` state-regression claim): falsified

## Origin

Directive `D-CODEX-ATLAS-DEFECT-2-STATE-REGRESSION-FALSIFICATION-AND-CONTINUATION`.
Claim under test: a prior process (N) may reach `NodeState.ACTIVE` while
durable `LoopState` remains `LEASED`; after process death, a fresh
governor (process N+1) reconstructs the node through
`DISCOVERED -> READY -> LEASED`; therefore the logical node "regresses"
`ACTIVE -> LEASED`. The directive required this be falsified or proven
against current repository truth before any remediation, per its own
"PROVE FIRST, PATCH SECOND" operating principle.

## Repository truth at time of investigation

- `CURRENT_MAIN_HEAD` = `2cee148947c01b9b228d8576c72cf8190bf6966a`
- `CURRENT_MAIN_TREE` = `b59c9f77fd9fef048b7b869027683e44358c9a6f`
- Investigated in worktree branch `fix/orch-governor-dependency-enforcement`
  (based on the above main head); `git diff origin/main --stat` confirmed
  `dag.py` and `rehydration.py` — the two files this investigation turns
  on — are byte-identical to `origin/main`, untouched by that branch's
  own (unrelated, dependency-enforcement) changes.
- The claim itself was **not new**: `docs/evidence/D-203-...md` and
  `docs/evidence/D-205-...md` (both already merged, both read in full
  before any conclusion here) had already investigated closely related
  ground. D-205 in particular contains a section, "A note on ACTIVE,
  honestly stated," asserting exactly the conclusion this record
  independently re-derives and empirically re-proves below — this
  record does not take that assertion on faith; every claim in it was
  re-verified against current source and a fresh, real-subprocess test.

## Step 1 — precise claim, and which of the two candidate semantics is real

Two materially different claims were distinguished per the directive's
own framing:

- (a) the system *applies or records* an `ACTIVE -> LEASED` DAG
  transition on an existing `WorkNode`, or
- (b) a new governor reconstructs the last durably-provable checkpoint
  through legal transitions on a **new** `WorkNode` object, leaving
  whatever the old (dead-process, non-durable) object was doing
  irrelevant.

## Step 2 — state-machine contract

`dag.ALLOWED_TRANSITIONS[NodeState.ACTIVE]` =
`{VERIFYING, REMEDIATING, BLOCKED, OWNER_HELD}` — **`LEASED` is not in
this set.** If the system ever attempted `ACTIVE -> LEASED` on a real
`WorkNode`, `apply_transition()` would raise `IllegalTransitionError`
immediately (`dag.py`, `_check_legal_transition`). No repository
contract, ADR, or test asserts a monotonicity guarantee stronger than
this table — grepped `monotonic`, `regression`, `checkpoint`,
`replay`, `idempotent`, `exactly once` across `docs/`, `src/`,
`tests/`: no such stronger contract exists.
`GLOBAL_ENUM_MONOTONICITY`, `CROSS_PROCESS_LOGICAL_STATE_MONOTONICITY`,
`TRANSITION_RECORD_MONOTONICITY` are all **not required** by anything
in this repository beyond the transition table itself.

## Step 3/4 — real reproduction and transition-history capture

`tests/unit/test_orchestration_autonomy_rehydration.py::
test_real_subprocess_recovery_after_crash_at_active_is_not_a_state_regression`
(new). Two genuinely separate `python -c` OS subprocesses, sharing only
the filesystem — not two objects in one interpreter:

- **Process N**: real `governor.lease()`, then a real
  `governor.execute_leased(lease_id)` call — the exact call that moves
  a node to `ACTIVE` — confirmed via `governor.snapshot()` immediately
  after. Durable `LoopState` was saved at `LEASED` *before*
  `execute_leased()` ran and never re-saved after (mirroring exactly
  what a genuine crash in this window leaves on disk, per D-203's own
  analysis of `_dispatch_leased()`). Process exits here — no further
  state is written anywhere.
- **Process N+1**: a brand-new `AutonomousGovernor`
  (`governor.snapshot().nodes == ()` asserted before rehydration
  runs), then the real production sequence
  `rehydrate_governor()` → `AutonomousLoop(...).tick()` — the same
  sequence `cli.py::run_governor_loop_tick()` runs, reproduced inline
  (not the black-box wrapper) specifically so the test can read
  `governor._transitions` directly.

Result (from the real transition log of the real object that ran, not
inferred):

```
PROCESS_N:
  execute_leased() -> node state ACTIVE (in memory only)
  durable LoopState.phase == LEASED (never re-saved)
  CRASH (process exit)

PROCESS_N+1:
  fresh governor, 0 nodes
  rehydrate_governor():
    DISCOVERED -> READY   (mark_ready)
    READY -> LEASED       (restore_lease)
  node state immediately after rehydration: LEASED
  loop.tick():
    LEASED -> ACTIVE      (execute_leased(), re-run)
    ACTIVE -> VERIFYING -> CERTIFIED -> ... (apply_observed_result)
  final phase != FAILED_CLOSED
  final lease_id == the same lease_id from process N
```

`ACTIVE_TO_LEASED_TRANSITION_RECORDED` = **NO** — asserted directly:
every transition record landing on `to == "LEASED"` across both the
rehydration pass and the full tick that follows is checked, and none
has `from == "ACTIVE"`.

`OLD_ACTIVE_NODE_MUTATED_BACKWARD` = **NO** — process N+1's governor
starts with zero nodes and never references process N's object (it
cannot: separate OS processes, separate address spaces). Its own
`package_id`-scoped transition sequence is exactly
`DISCOVERED -> READY -> LEASED`, the same legal forward sequence any
first-time `lease()` call produces.

## Step 5 — replay safety (the deeper question, checked directly)

Process N+1's `loop.tick()` genuinely calls `execute_leased()` a
*second* time for the same lease (process N had already called it once,
in a process that no longer exists). Whether this is a "duplicate
externally observable side effect" depends entirely on whether
`execute_leased()` has any side effect at all — checked directly, not
assumed:

- `governor.execute_leased()` (`governor.py`): transitions the node,
  builds a payload dict, calls `make_bundle()`, returns the bundle.
- `evidence.make_bundle()` (`evidence.py`): `digest =
  hash_payload(payload); return EvidenceBundle(...)` — pure
  computation, zero I/O.
- The only function in that module that touches disk is
  `write_bundle()`, a **separate** function `execute_leased()` never
  calls.

`EXECUTION_HOST = IN_PROCESS` (the only host reachable through this
recovery path today — `ExecutionHostClass.EXTERNAL_AGENT` dispatch
goes through `_dispatch.dispatch_once()`, a different, already
idempotency-guarded branch of `_dispatch_leased()`, not through
`execute_leased()` at all):

```
SIDE_EFFECTING = NO
REPLAY_SAFE = YES
IDEMPOTENT = YES (pure function of lease_id/package_id/base_pin — no
                  hidden state, confirmed by reading make_bundle())
RESULT_BOUND = N/A (nothing to bind a result to; no external artifact)
DUPLICATE_EXECUTION_RISK = NO
DURABLE_PROGRESS_REQUIRED = NO (for this host; see below for the
                                architectural caveat)
```

Because process N crashed *before* `apply_observed_result()` ever ran,
process N never persisted or externally observed a result either — so
this is not even "replaying" an action that already happened from any
observer's perspective; it is completing, for the first and only
observable time, a pure computation whose first attempt died unread.

## Step 6 — classification

**`DEFECT_2 = NOT_A_CURRENT_RUNTIME_DEFECT`** (Case C). No
`ACTIVE -> LEASED` transition is ever applied or recorded; the
transition table does not even permit it; fresh reconstruction walks
only legal forward transitions on a new object; no stronger repository
monotonicity contract exists to violate; the one currently reachable
execution host (`IN_PROCESS`) is side-effect-free and therefore
replay-safe; no duplicate external effect was reproduced or is
possible today.

Per the directive's Case C requirement, the state machine was **not**
redesigned — no `ACTIVE -> LEASED` edge was added to
`ALLOWED_TRANSITIONS`, no production code changed at all. The residual
architectural constraint is recorded, matching D-205's own prior
language:

`FUTURE_SIDE_EFFECTING_HOST_REQUIRES_DURABLE_EXECUTION_PROGRESS = YES`
— any future `ExecutionHostClass` whose execution step performs a real
external side effect (file mutation, commit, external dispatch,
network call, spend) would need its own durable progress record before
this same "always reconstruct to the last durable checkpoint, re-run
forward from there" approach could safely extend to it. No such host
exists on this tree today (`EXTERNAL_AGENT` dispatch is a different,
already-guarded code path, not `execute_leased()`).

## Test requirement (directive §7)

Existing coverage (`test_real_subprocess_recovers_leased_pilot_node_after_crash`)
proved cross-process recovery from a crash *at* `LEASED` (before any
execution). It did not drive process N to `ACTIVE` first — the exact
disputed window. New test
`test_real_subprocess_recovery_after_crash_at_active_is_not_a_state_regression`
closes that gap: real separate-process reproduction, transition-history
assertions (both A/B/C/D/E from the directive's step 4), replay-safety
assertions, and terminal-outcome assertions, so a future developer
re-reading the transition table cannot reinterpret this as a real
regression without this test failing first.

## Validation

- `pytest tests/unit/test_orchestration_autonomy_rehydration.py
  tests/unit/test_orchestration_autonomy_loop.py
  tests/unit/test_orchestration_autonomy.py`: 116 passed.
- `ruff check tests/unit/test_orchestration_autonomy_rehydration.py`:
  clean.
- No production code changed — no `mypy src` delta possible; ran
  anyway for due diligence: `Success: no issues found in 393 source
  files`.

## Independent verification

Not self-certified. Per standing project rule, this classification and
the new test require independent adversarial review before being
treated as final — specifically challenging the crash-window
reproduction's authenticity, the replay-safety argument, and whether
`NOT_A_CURRENT_RUNTIME_DEFECT` is the correct call rather than a
premature dismissal. See the IV round recorded alongside this
directive's return packet.

## Certification state

Investigation complete, test-only change, no production code modified.
`GOVERNED_AUTONOMY_ACTIVE` status unaffected by this record.
