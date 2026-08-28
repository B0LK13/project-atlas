# D-200 — ORCHAUT-010: owner gates C-F select/lease-boundary remediation

## Context

PR #633 (`fix/orchaut-010-owner-gates-c-f-enforcement`, head
`d8490cc250434a82215d97e8cf119a9f7c31504a`) added four symmetric
`AutonomousGovernor.request_*` primitives for owner gates C-F and made
`AutonomousLoop.refuse_owner_actions()` iterate all six `OwnerGateKind`
values instead of only gate A. Two automated reviewers (Copilot PR
reviewer, `chatgpt-codex-connector`) independently flagged, in unresolved
review threads, that these were opt-in definitions with no call site: a
`READY` `WorkNode` carrying owner_gate C/D/E/F was still selected by
`select_next`, then leased and (for `IN_PROCESS` hosts) fully executed and
certified by `AutonomousLoop._select_and_lease()` / `execute_leased()`,
without any of the new methods ever being invoked.

## Independent verification performed

Read `continuation.select_next` and `AutonomousLoop._select_and_lease`
directly (not the PR description) at the exact PR head. Confirmed the
defect precisely:

- `continuation.py` line 46 (pre-fix): `if node.owner_gate is not None and
  node.state != NodeState.READY: continue` — dead code. This line only
  runs inside `for node in ready`, where every node's `state` is already
  `READY` by construction (`ready = [n for n in nodes if n.state in
  _RUNNABLE]`, `_RUNNABLE = {READY}`), so `node.state != NodeState.READY`
  is always `False` and the `continue` never fires. A `READY` node tagged
  with owner_gate C/D/E/F falls through and is returned as the selected
  package.
- `loop.py` `_select_and_lease` line 453 (pre-fix) had the identical
  dead-code pattern as a second (equally ineffective) check before
  `governor.lease(...)`.
- Verdict on PR #633 as submitted: **BLOCK** — the PR's stated claim
  ("owner gates C/D/E/F now fail closed") does not hold on the real
  select -> lease -> dispatch path. The new `request_*` methods and the
  widened `refuse_owner_actions()` loop are real but are never called by
  `tick()` / `_select_and_lease()` / `select_next()`, so they provide no
  enforcement unless a caller voluntarily invokes them. Confirmed
  independently; matches the unresolved Copilot/Codex findings.

## Remediation applied (this commit)

Same candidate/branch, following "self-remediate an already-established
requirement" (the requirement — gates C-F fail closed at the real
selection boundary, matching A/B — is the PR's own stated purpose and the
`LOOP_CAN_BYPASS_OWNER_GATE = NO` module contract; no new owner semantic
decision was required):

- `continuation.select_next`: any `ready` node with `owner_gate is not
  None` is now always skipped (never selected), and the stop reason
  reported to the caller is `OWNER_GATE` (not `NO_ELIGIBLE_WORK`) when an
  owner-gated `READY` node was the only candidate.
- `loop.AutonomousLoop._select_and_lease`: the matching defense-in-depth
  check before `governor.lease(...)` now stops unconditionally on any
  `owner_gate is not None`, not only when `state != READY` (which was
  never true at that point).
- Added regression coverage that was previously absent: all existing
  owner-gate tests only exercised `OWNER_HELD` / `MERGE_ELIGIBLE` states;
  none exercised a `READY` node carrying an owner_gate tag, which is
  exactly the gap. New tests:
  - `test_continuation_never_selects_ready_owner_gated_node` (parametrized
    C/D/E/F) — `select_next` on a lone `READY` owner-gated node returns
    `next_package_id=None`, `stop_reason=OWNER_GATE`.
  - `test_continuation_skips_owner_gated_ready_node_for_ungated_sibling` —
    a `READY` owner-gated node is skipped in favor of an ungated sibling.
  - `test_ready_owner_gated_node_never_leased_or_dispatched` (parametrized
    C/D/E/F, end-to-end through `AutonomousLoop.run_until_stop()`) — zero
    dispatch-port calls, `dispatched=False`, `stop_reason=OWNER_GATE`, node
    remains `READY` (not leased, not executed, not certified).

## Local validation (this session, exact worktree head)

Run from an isolated worktree at the PR branch tip plus this commit,
`PYTHONPATH` pointed at the worktree's own `src/` (the machine's global
editable install resolves to an unrelated stale worktree —
`D:\atlas-worktrees\aug26-d027-main` — noted here so the next session
doesn't lose an hour to the same trap):

- `pytest tests/unit/test_orchestration_autonomy.py
  tests/unit/test_orchestration_autonomy_loop.py`: 53/53 passed, 0
  failed.
- `pytest -k "orchestration or autonomy"`: 292/292 passed, 0 failed, 4287
  deselected.
- `ruff check` (touched files, then full repo): clean.
- `mypy` (touched files): clean. Full-repo `mypy src`: 1 pre-existing,
  unrelated failure (`connect_perf.py` uses the POSIX-only `resource`
  module — fails under Windows mypy regardless of this change; not
  touched by this PR or this fix).

## Certification state

`MERGE_AUTHORIZATION` unchanged: still requires owner action per
`GOVERNANCE.md`. **This fix is not self-certified.** The implementer of
this remediation (this session) must not also serve as its Independent
Verifier for the same candidate — a separate agent/session must reproduce
this validation and adjudicate PASS/BLOCK before certification, and
exact-head hosted CI must be green at the new head before any merge.
