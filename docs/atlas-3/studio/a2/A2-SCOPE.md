# AS-STUDIO-A2 — scope reconciled from repository truth

```text
BUTTON != MUTATION
REQUESTED != CLAIMED
PREVIEW != EXECUTION
AVAILABLE != AUTHORIZED
STUDIO_UI != AUTHORITY
REUSE_BEFORE_REIMPLEMENT
NO_PARALLEL_CONTROL_PLANE
AS_STUDIO_A2_IMPLEMENTATION = A2_001_IMPLEMENTED_IN_LANE
AS_STUDIO_A2_SCOPE = READY
DISPATCH_STEAL_AUTO = NOT_STARTED
```

This document **challenges** PHASES / #746 wording that can be misread as
“A2 ships mutation buttons that write.” It does not implement A2.

## What PHASES / #746 said

| Prior planning | Risk if taken literally |
|---|---|
| A2: “Governed claim/dispatch/handoff/open-worktree/terminal” | Implies a bundle of write paths in one package |
| Requirements register §56: mutations with denial tests | Easy to implement UI-first with disabled buttons as “governance” |
| Exit evidence: lease/state race, idempotency, PTY, audit | Correct *eventually*, but not the first vertical |

## Repository truth (must bind A2)

| Surface | Maturity | Mutation? |
|---|---|---|
| F12 `frontier_matrix` / `OWNERSHIP_CLAIM` | Implemented; action-class + rankings | Projection only |
| F04 `emitter.emit_event` (`OWNER_CLAIMED`) | Race-safe lane mutex; capability-checked | **Yes** (event bus) |
| F11 `steal.plan_steal` / `execute_steal` | Plan RO; execute claims via emitter | Execute = claim write |
| F06 `dispatch.plan_dispatch` / `execute_dispatch` | Sibling CI/IV lanes; dry-run | **Yes** (CI + IV_REQUEST) |
| F08 `handoff.build_handoff` | Generation only; TOCTOU stale fail | **No delivery** |
| Studio A0/A1 | RO snapshot + Mission Control | **Zero mutation API** |

## Reconciled A2 stance

1. **A2.0 is the governed intent + authorization boundary**, not “every mutation
   surface at once.”
2. **BUTTON ≠ MUTATION.** A Mission Control control may emit a *typed intent*
   (REQUESTED). Execution is a separate control-plane step that may REFUSE.
3. **Do not invent Studio eligibility.** Candidates come from F12 / F15 /
   Mission Control projections only.
4. **First vertical = one action type** (see `A2-FIRST-WORK-PACKAGE.md`):
   governed **CLAIM** of an eligible unowned/runnable lane.
5. Dispatch, handoff delivery, worktree/PTY, steal-as-policy, and terminal
   attach as later A2.x packages behind the same intent model.

## Challenge: BUTTON → MUTATION

Forbidden patterns:

- UI “Claim” that calls `atlas-dag steal` / `emit` directly from Studio process
  without a typed intent + control-plane decision record.
- Disabled-in-UI-only “safety” with a hidden write path.
- Treating attention rank / `AVAILABLE` / dry-run `WOULD_CLAIM` as authorization.
- Caching a prior authorize decision across a new MC fingerprint.

Required pattern:

```text
MC state → action candidate → preview/why/impact
  → policy check (capability, freshness, agent bind)
  → governed REQUEST (intent)
  → control plane evaluate
  → EXECUTE or REFUSE + evidence
```

## Non-goals (A2.0)

- Merge / force-merge / IV receipt minting.
- Parallel Studio ownership engine.
- Tauri-specific chrome (CLI/API intent surface first).
- Self-authorization inside `atlas_studio`.

## Dependency

```text
A1 TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED (done in lane)
+ F1–F16 claim/emit/steal/dispatch primitives available
→ A2 scope READY
→ AS-STUDIO-A2-001 IMPLEMENTED_IN_LANE (OWNERSHIP_CLAIM)
→ DISPATCH / STEAL_AUTO = NOT_STARTED
```
