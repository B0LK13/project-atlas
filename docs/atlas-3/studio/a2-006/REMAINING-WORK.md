# Remaining work — mission-session production readiness

```text
GOAL_STATUS             = ACTIVE → drain then BLOCKED_EXTERNAL
MERGE_AUTHORIZATION     = NOT_GRANTED
PRIOR_BEHAVIORAL_NOTE   = 1bca04e3 / docs tip b9fd932d superseded; do not reclaim
PRESERVE_UNDER_VERIFY   = tip at push time (see ATLAS-DOC-RECEIPT)
```

## Implemented (local this cycle)

- Unbound decision (`intent_id` null) → MISMATCHED_BINDING (not PENDING_EXECUTE)
- Bounded `lifecycle.snapshot_consistency` (COHERENT / INCOHERENT / UNPROVEN)
- `SNAPSHOT_INCONSISTENT` session state + recovery guidance
- Cross-process CLI acceptance (subprocess `-m atlas_studio`) with labeled fixtures
- Package `__main__` + `cli.py` `__main__` so module invocation actually runs
- Unreadable-file READ_ERROR coverage

## External only (do not poll-loop)

| Claim | Status |
|---|---|
| Exact-head CI SUCCESS | PENDING on tip after push |
| Formal IV | NOT_STARTED (owner; prior #788 IV does not transfer) |
| Merge | NOT_GRANTED |
| #786 task-context | UNAVAILABLE |
| Power-loss durability | NOT claimed |
| Multi-file FS atomic snapshot | NOT claimed (identifier-bounded check only) |

Stop manufacturing gaps once only this table remains.
