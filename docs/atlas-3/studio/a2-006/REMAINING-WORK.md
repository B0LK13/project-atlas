# Remaining work — mission-session production readiness

```text
GOAL_STATUS             = ACTIVE (overnight continuation)
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Implemented (local)

- Byte-accurate snapshot load; corrupt JSON → CORRUPT_INPUT
- Binding / conflict / fingerprint / persistence / orphan-tmp (prior)
- CLI exit codes for mission-session
- Control-plane observation + task-context UNAVAILABLE explicit

## Not established

| Claim | Status |
|---|---|
| Exact-head CI | PENDING / prior cancels |
| Formal IV | NOT_STARTED |
| Merge | NOT_GRANTED |
| Power-loss durability | NOT claimed by process tests |
| Multi-file FS atomic snapshot | NOT claimed (binding checks only) |

## Next engineering

1. Soft schema validation on load (fail → MALFORMED/CORRUPT, no authority grant)
2. Empty/non-UTF8 edge coverage if gaps remain
3. After CI green: freeze SUBJECT once for Formal IV (owner dispatch)
