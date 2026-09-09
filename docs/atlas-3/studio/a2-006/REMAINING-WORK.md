# Remaining work — mission-session production readiness

```text
GOAL_STATUS             = ACTIVE (overnight continuation)
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Implemented (local)

- Byte-accurate snapshot load; corrupt/empty/non-UTF8 → CORRUPT_INPUT
- Binding / conflict / fingerprint / persistence / orphan-tmp
- CLI exit codes for mission-session
- Optional `--strict-schema`
- Claim evaluate/execute intent load via snapshot_load
- Control-plane observation + task-context UNAVAILABLE explicit
- ACCEPTANCE-DEMO.md (local / verifier prep)

## Not established

| Claim | Status |
|---|---|
| Exact-head CI | PENDING / prior cancels |
| Formal IV | NOT_STARTED |
| Merge | NOT_GRANTED |
| Power-loss durability | NOT claimed by process tests |
| Multi-file FS atomic snapshot | NOT claimed (binding checks only) |

## Next engineering

1. After exact-head CI green: freeze SUBJECT once for Formal IV (owner dispatch)
2. #786 landing → flip task-context AVAILABLE (external)
3. Stop manufacturing gaps when only external blockers remain
