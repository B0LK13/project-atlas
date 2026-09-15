# AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001

**STACKED_DEPENDENCY** = PR435 (`AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001`)  
**MERGE_ORDER** = PR433 → PR435 → MISSION_RECONCILER  
**MERGE_AUTHORIZATION** = NOT_GRANTED  

## Purpose

Closed-loop work producer subordinate to the PRIMARY GOVERNOR.

```
project reality → unmet objectives → DAG nodes → real workers → receipts → successors → repeat
```

## Non-goals

- Not a second coordinator / planner governor
- Does not grant merge authority
- Does not count READY cards as active workers

## Persistence

Under `.atlas/orchestration/sdk-runtime/`:

| File | Role |
|------|------|
| `mission-objectives.json` | O1–O6 durable objectives |
| `mission-nodes.json` | Work DAG nodes |
| `mission-workers.json` | Real worker bindings only |
| `mission-reconciler-state.json` | Generations / sequences |
| `mission-receipts.jsonl` | Receipt index |

## Invariants

- `HEARTBEAT ≠ PROJECT_PROGRESS`
- `SYNTHETIC_ACTIVE_WORKER_COUNT = 0`
- `TERMINAL_RECEIPT_WITHOUT_DAG_RECONCILIATION = 0`
- Empty READY → mission reconcile before idle
- `DUPLICATE_PACKAGE_DISPATCH = 0` via idempotency keys
- `SURFACE_OVERLAP_CHECKED = YES`

## Integration

`resident_driver._try_closed_loop` optionally imports this module. PR435 remains
liveness-only if the module is absent.
