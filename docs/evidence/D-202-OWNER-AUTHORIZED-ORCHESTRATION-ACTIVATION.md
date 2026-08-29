# D-202 — Owner-authorized activation of the governed orchestration/autonomy stack

## Directive being consumed

Owner directive text (this session, 2026-08-28), in sequence:

- `D-OWNER-ACTIVATE-GOVERNED-SHOWCASE-PATH` item 2: *"Owner intent is:
  `ACTIVATE_FULL_GOVERNED_AUTONOMY = YES`. For the already-integrated and
  independently verified orchestration packages: 001A, 001B, 001C+R1,
  001D, RESULT_BINDING, 001E, record/perform whatever repository-defined
  activation or authorization transition is required. Do not invent a
  new activation mechanism if none exists. Do not re-merge code already
  on main. The activation is authorized only after PR633 is integrated
  and its A–F gate guarantees are live on main."*
- `D-GOVERNED-AUTONOMY-EXECUTION-WAVE` Lane 1: *"Discover the
  repository-defined activation state/mechanism... Do NOT invent a
  ceremonial activation mechanism merely because prior prose says
  'activation record.' First determine from source/backlog/governance
  whether activation requires: code mutation; configuration;
  state/metadata transition; certification record; or simply consuming
  existing owner authorization. If existing repository semantics
  determine the required action, execute it autonomously... Before
  declaring autonomy active, prove: A–F gates fail closed on actual
  selection/lease/execution boundaries; no autonomous merge/waiver/
  destructive/spend path bypass exists; result-binding and replay
  protections are live; relevant current-main regression suites pass; no
  unresolved P0/P1 autonomy defect remains."*

## What "activation" actually is in this repository (determined, not invented)

Grepped `docs/backlog.md` and `WORKLOG.md` for the established pattern
across every prior certified-but-unmerged package in this project's
history (dozens of examples, e.g. AS-CODER-ALPHA-CAPTURE-002/D-042,
AS-2.1-MCP-BRIEF-001, every AT3-0xx isolated package). The pattern is
uniform and long-standing: a package moves from
`MERGE_AUTHORIZATION = NOT_GRANTED` to a granted state purely as a
**documentation/governance record** — `docs/backlog.md`'s per-package
status marker plus a `docs/evidence/D-NNN-....md` receipt citing the
owner's exact authorization and the verification it rests on. There is
no code-level "activation switch," feature flag, or runtime gate
separate from the `OwnerGateKind` A-F enforcement itself (confirmed by
grep: no `ATLAS_ORCH_ACTIVE`-style flag or equivalent exists anywhere in
`src/`). This matches `GOVERNANCE.md` stage 8 ("Baseline update —
Receipts/roadmap record the new certified tip when Owner accepts it").

**Therefore: activation here means exactly what the directive anticipated
as one of the listed possibilities — "simply consuming existing owner
authorization," recorded via the repository's own established
mechanism.** No new mechanism was invented. No code was re-merged (all
001A-001E code is already on `main`, unchanged by this record).

## Preconditions verified fresh on current main (not assumed)

Current main tip at time of this record:

```
MAIN_HEAD = 3c626408051e9de3f11061bff28bbd4c688ef68b
MAIN_TREE = 6d5e3993dd7a440f20800bd59fa917e5d87716fc
```

(Includes PR #633/ORCHAUT-010 merge `7bcb8ea2`, plus #421, #405, #634
merged afterward — all independently verified and merged separately;
none touch the orchestration/autonomy package under activation here
except #633 itself.)

1. **A–F gates fail closed on actual selection/lease/execution
   boundaries** — re-confirmed by reading the exact merged code on this
   tip directly (not re-trusting the PR description):
   - `continuation.py` `select_next`: any `ready` node with
     `owner_gate is not None` is unconditionally excluded from
     autonomous selection (line ~47).
   - `governor.py` `AutonomousGovernor.lease()`: raises
     `GovernorError(code="OWNER_GATE_REQUIRED")` for any `owner_gate`
     other than `A_PROTECTED_MAIN_MERGE` without an explicit
     `owner_grant=True` (line ~340) — this is the boundary
     `run_controlled_pilot()`/`continue_autonomous()` also pass through,
     so it isn't only enforced inside the 001E loop.
   - Gate A itself remains blocked at two independent, gate-agnostic
     layers: `request_merge()` (unconditional without a grant) and
     `dag.py::apply_transition()` (unconditionally rejects any
     transition to `MERGED`).
2. **No autonomous merge/waiver/destructive/spend path bypass exists** —
   same code paths as above; `LOOP_CAN_AUTHORIZE_MERGE = NO` /
   `LOOP_CAN_GRANT_WAIVER = NO` / `LOOP_CAN_EXPAND_OBJECTIVE = NO` remain
   structurally true (unchanged loop.py module contract, only the
   selection/lease boundary was hardened).
3. **Result-binding and replay protections are live** —
   `AS-ORCH-001D-RESULT-BINDING-001` (ORCH001DRB-001 through 007) is
   unchanged since its own 2026-08-28 independent verification (32/32
   tests + 15 adversarial frame-injection probes including real Windows
   `CreateProcess`, see WORKLOG "EOD convergence wave"); replay
   guards (`completed_dispatch_ids`, `completed_lease_ids`,
   `completed_result_digests`) in `loop.py` are unchanged by #633.
4. **Relevant current-main regression suites pass** — fresh run on this
   exact tip, in an isolated worktree with `PYTHONPATH` forced to it
   (the global editable install resolves to an unrelated stale
   worktree, confirmed and avoided): `pytest -k "orchestration or
   autonomy"` → **298 passed, 0 failed, 4312 deselected**. `ruff check
   src/project_atlas/orchestration/` and `mypy
   src/project_atlas/orchestration/autonomy/` (21 source files): both
   clean.
5. **No unresolved P0/P1 autonomy defect remains** — ORCHAUT-010 (the
   sole P0/P1 open against this stack, found during `ORCH001E-008`'s
   IV) is fixed and merged. The three `ORCH001E-008` non-blocking
   follow-ups: two (dead/misleading owner-gate guard; overstated
   `AUTONOMY-001` honesty marker) were resolved as a direct side effect
   of the ORCHAUT-010 fix; the third (P3 crash-recovery liveness gap,
   orphaned dispatch after a crash) is tracked separately (PR #635, not
   yet certified) — it is an operability gap ("fail-stuck, not
   fail-dangerous"), not an authority-boundary defect, and does not
   block this activation per the directive's own stated bar (P0/P1
   autonomy defects, not P3 operability gaps).

## CORRECTION (2026-08-28, same day, before this record's own PR merged)

An independent verifier reviewing a separate, unrelated PR (#637)
adversarially discovered, and this session independently reproduced, that
`run_governor_loop_tick()` — the function behind the real CLI command
`atlas orchestrator governor-loop-tick` — constructs a brand-new, empty
`AutonomousGovernor` on every invocation, with no node
discovery/rehydration step at all. This means the real CLI entry point
cannot originate new work or recover interrupted work across separate
process invocations — it only functions within a single long-lived
Python process that manages its own governor lifecycle (exactly how
every existing test and the pilot flow already use it). Full detail:
`docs/evidence/D-204-GOVERNOR-LOOP-TICK-NO-NODE-REHYDRATION.md`.

This does **not** change preconditions 1-3 above (A-F gate enforcement,
no bypass paths, result-binding/replay protections) — those are about
selection/lease/execution logic that behaves correctly whenever nodes
ARE present, regardless of how they got there. It **does** mean the
"Result" block below is corrected: `GOVERNED_AUTONOMY_ACTIVE` is
downgraded from an unqualified `YES` to `PARTIAL`, scoped precisely to
what was actually verified, with the CLI-level gap stated explicitly
rather than implied to be solved. This correction was made in the same
PR, before merge, rather than as a silent fix-up after the fact.

## What is NOT claimed

- This does not claim `ORCH001D-012` (authentic Cursor dispatch
  acceptance) is satisfied — it remains separately outstanding and is
  the next lane.
- This does not claim the P3 crash-recovery gap (PR #635) is fixed on
  `main` — it is not yet merged.
- This does not grant any NEW owner gate exception, waiver, or scope
  beyond what ORCHAUT-010 itself already closed.
- `AUTOMATIC_MERGE`, `LOOP_CAN_AUTHORIZE_MERGE`, and every other
  `= NO` honesty flag in the per-package sections below remain exactly
  as true as they were before this record — activation of the
  orchestration *stack* is not a grant of merge authority to the loop
  itself, which GOVERNANCE.md reserves to the Owner permanently.

## Result

`docs/backlog.md` per-package `MERGE_AUTHORIZATION` markers updated for
AS-ORCH-001A, AS-ORCH-001B, AS-ORCH-001C(+R1), AS-ORCH-001D,
AS-ORCH-001D-RESULT-BINDING-001, AS-ORCH-001E, and AS-ORCH-AUTONOMY-001
from `NOT_GRANTED` to `GRANTED`, each citing this record. `ORCHAUT-010`'s
checklist item is checked off (previously reopened, now fixed and
merged as `7bcb8ea2`). `OWNER_GATES_A_F` reverts from
`PARTIALLY_IMPLEMENTED` back to `IMPLEMENTED` under
`AS-ORCH-AUTONOMY-001`, now genuinely accurate. `ORCHAUT-013` and
`ORCH001E-009` ("Owner merge gate (not this package)") remain
unchecked — activation of the stack is not, and does not claim to be,
a grant of automatic merge authority.

```
GOVERNED_ORCHESTRATION_STACK = ACTIVE
GOVERNED_AUTONOMY_ACTIVE = PARTIAL
OWNER_GATE_ENFORCEMENT_AT_SELECTION_LEASE_EXECUTION = YES (verified)
GOVERNOR_LOOP_TICK_CLI_CROSS_PROCESS_ORIGINATION = NOT_FUNCTIONAL (unproven; see 2026-08-29 update)
GOVERNOR_LOOP_TICK_CLI_CROSS_PROCESS_RECOVERY = FUNCTIONAL (2026-08-29, see update below)
LOOP_CAN_BYPASS_OWNER_GATE = NO
LOOP_CAN_AUTHORIZE_MERGE = NO
```

`GOVERNED_AUTONOMY_ACTIVE = PARTIAL` is the accurate summary: the
governance/authority boundary (what this record's own preconditions
verified) is live and correct; the loop's operational reach as a real,
repeatable CLI command was not yet functional beyond a single process's
lifetime, per D-204 — the update below covers exactly one of the two
gaps D-204 found. "Activation" here authorized what was actually
verified — it did not, and should not be read to, certify
`governor-loop-tick` as production-usable end to end.

## UPDATE (2026-08-29): ORCH001E-011 closes the recovery half of D-204

`ORCH001E-011` (PR #638) implements real governor/lease rehydration in
`rehydration.py`, reusing the existing `AS-ORCH-DURABLE-LEASE-PROJECTION-001`
projection (no second, competing persisted-DAG model). This closes the
`GOVERNOR_LOOP_TICK_CLI_CROSS_PROCESS_RECOVERY` gap D-204 identified, and
does so with the same class of proof D-204 itself demanded: not a unit test
against in-memory objects, but `test_real_subprocess_recovers_leased_pilot_node_after_crash`
-- two genuinely separate OS processes (`subprocess.run([sys.executable, "-c", ...])`),
the first leasing a node and exiting mid-flight (the crash window), the
second a fresh `python -m` invocation of the real `run_governor_loop_tick()`
CLI entrypoint recovering and completing it. Independently re-run
2026-08-29 (not merely re-trusted from the PR): **PASS**.

`GOVERNOR_LOOP_TICK_CLI_CROSS_PROCESS_ORIGINATION` is **not** upgraded by
this update, and this is a deliberate, evidence-based distinction, not an
oversight: ORCH001E-011 also fixed the origination code path itself
(`_originate()` now runs the READY transition after `ingest_discovery()`,
matching `run_controlled_pilot()`'s existing behavior), but this cannot be
demonstrated end-to-end today because the real `discover()` implementation
has never returned an eligible non-pilot candidate -- every hardcoded
candidate in `discovery.py` is `eligible=False` (see
`test_originate_marks_newly_discovered_node_ready`'s own docstring, which
states this plainly and monkeypatches `discover()` to prove the origination
*logic* in isolation instead). So: the origination bug is fixed, but
cross-process origination of genuinely new work remains unproven, not
merely unfixed -- a real `discover()` capable of finding eligible non-pilot
work is a separate, larger piece of scope, not part of ORCH001E-011.

`GOVERNED_AUTONOMY_ACTIVE` stays `PARTIAL` for exactly this reason -- this
update does not claim `FULL`, only that one of D-204's two named gaps is
now genuinely closed and independently re-verified, and the other remains
open and precisely characterized rather than left stale.
