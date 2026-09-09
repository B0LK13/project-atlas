# ADR-035 — Studio governed action intent (not self-authorization)

**Status:** accepted for AS-STUDIO-A2-001 lane implementation (OWNERSHIP_CLAIM);
broader A2.x surfaces remain NOT_STARTED
**Date:** 2026-09-09
**Package:** `AS-STUDIO-A2` / `AS-STUDIO-A2-001`
**Related:** [ADR-034](./ADR-034-studio-daemon-authority.md) (Studio projection; daemon authority)

## Design laws

```text
STUDIO_UI != AUTHORITY
BUTTON != MUTATION
REQUESTED != CLAIMED
PREVIEW != EXECUTION
AVAILABLE != AUTHORIZED
STUDIO_NEVER_SELF_AUTHORIZES
REUSE_BEFORE_REIMPLEMENT
```

## Context

A1 Mission Control projects coordination truth and human attention without
mutation APIs. A2 must introduce human/agent-triggered actions (claim,
dispatch, handoff, worktree, terminal) without collapsing UI controls into
authority. Repository already has mature `atlas_dag` claim/emit/steal/dispatch
primitives; Studio must not reimplement or bypass them.

## Decision

1. **Studio produces typed action intents** (`ATLAS_STUDIO_ACTION_INTENT_V1`
   sketch in `docs/atlas-3/studio/a2/A2-ACTION-INTENT-MODEL.md`), bound to a
   Mission Control fingerprint and freshness window.
2. **Atlas control plane evaluates** validity, authorization, freshness, and
   TOCTOU; then executes or refuses. Studio never sets authorization grants.
3. **First work package** (`AS-STUDIO-A2-001`) is governed **OWNERSHIP_CLAIM**
   of an eligible unowned/runnable lane, reusing F12 + F04 emitter — not
   dispatch-first, not UI-direct steal.
4. **Attention / ranking / availability remain non-authoritative** (A1 laws).

## Consequences

- A2 implementation starts only after intent schema + denial tests land.
- Steal/dispatch/handoff/worktree attach as later packages on the same bridge.
- ADR-034 remains binding: Studio crash still ≠ agent task termination;
  Studio process still grants no mutation authority by presence alone.

## Honesty

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE
DISPATCH_STEAL_AUTO = NOT_STARTED
CI_PASS != FORMAL_IV
MERGE_AUTHORIZATION = NOT_GRANTED by this ADR alone
STUDIO_MUTATION_AUTHORITY = NONE (Studio never self-authorizes)
```
