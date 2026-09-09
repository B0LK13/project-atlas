# Atlas Studio A2 — governed action intents

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE (OWNERSHIP_CLAIM only)
DISPATCH_STEAL_AUTO = NOT_STARTED
STUDIO_MUTATION_AUTHORITY = NONE (Studio never self-authorizes)
BUTTON != MUTATION
REQUESTED != CLAIMED
PREVIEW != EXECUTION
AVAILABLE != AUTHORIZED
MERGE_AUTHORIZATION = NOT_GRANTED
FORMAL_IV = NOT_STARTED
```

A2 turns Mission Control **attention / action candidates** into **typed
governed action intents**. Studio may propose and preview; Atlas control plane
evaluates validity, authorization, freshness, and executes or refuses.
Studio never self-authorizes.

## Documents

| Document | Role |
|---|---|
| [A2-SCOPE.md](./A2-SCOPE.md) | Reconciled scope; challenges BUTTON→MUTATION |
| [A2-ACTION-INTENT-MODEL.md](./A2-ACTION-INTENT-MODEL.md) | Typed intent model |
| [A2-AUTHORITY-BOUNDARY.md](./A2-AUTHORITY-BOUNDARY.md) | Studio vs control-plane authority |
| [A2-FIRST-WORK-PACKAGE.md](./A2-FIRST-WORK-PACKAGE.md) | `AS-STUDIO-A2-001` — first governed CLAIM |
| [A2-EVIDENCE.md](./A2-EVIDENCE.md) | Lane evidence / validation |
| ADR | [ADR-035](../../../adr/ADR-035-studio-governed-action-intent.md) |

## Dependency

```text
A0 TECHNICALLY_COMPLETE
+ A1 TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED
→ A2 scope READY
→ AS-STUDIO-A2-001 IMPLEMENTED_IN_LANE
→ DISPATCH / STEAL_AUTO / handoff delivery / worktree = NOT_STARTED
```

## Non-goals (remaining A2.x)

- No general mutation surface on package root.
- No steal/write shortcuts that bypass intent + control-plane evaluation.
- No dispatch / merge / IV mutation / PTY in A2-001.
