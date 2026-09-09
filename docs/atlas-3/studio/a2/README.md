# Atlas Studio A2 — governed action intents (docs)

```text
AS_STUDIO_A2 = SCOPE_READY / IMPLEMENTATION_NOT_STARTED
STUDIO_MUTATION_AUTHORITY = NONE (until control-plane-authorized execution)
BUTTON != MUTATION
REQUESTED != CLAIMED
PREVIEW != EXECUTION
AVAILABLE != AUTHORIZED
MERGE_AUTHORIZATION = NOT_GRANTED
```

A2 turns Mission Control **attention / action candidates** into **typed
governed action intents**. Studio may propose and preview; Atlas control plane
evaluates validity, authorization, freshness, and executes or refuses.
Studio never self-authorizes.

## Documents

| Document | Role |
|---|---|
| [A2-SCOPE.md](./A2-SCOPE.md) | Reconciled scope; challenges BUTTON→MUTATION |
| [A2-ACTION-INTENT-MODEL.md](./A2-ACTION-INTENT-MODEL.md) | Typed intent schema sketch |
| [A2-AUTHORITY-BOUNDARY.md](./A2-AUTHORITY-BOUNDARY.md) | Studio vs control-plane authority |
| [A2-FIRST-WORK-PACKAGE.md](./A2-FIRST-WORK-PACKAGE.md) | `AS-STUDIO-A2-001 READY` — first governed CLAIM |
| ADR | [ADR-035](../../../adr/ADR-035-studio-governed-action-intent.md) |

## Dependency

```text
A0 TECHNICALLY_COMPLETE
+ A1 TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED
→ A2 scope READY
→ AS-STUDIO-A2-001 implementation NOT_STARTED
```

## Non-goals (this folder)

- No mutation CLI/API implementation.
- No Studio-side claim/dispatch/merge/kill paths.
- No steal/write shortcuts that bypass intent + control-plane evaluation.
