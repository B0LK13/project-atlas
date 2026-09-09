# AS-STUDIO-A2-006 — Mission Session Continuity

```text
AS_STUDIO_A2_006                   = IMPLEMENTED_IN_LANE
BASE_FREEZE                        = #788 tip 10df59fb (validation cycle closed)
FORMAL_IV                          = NOT_STARTED (new candidate; does not inherit 4904125f)
MERGE_AUTHORIZATION                = NOT_GRANTED
```

Coherent mission session packet composing journey pointers, intent continuity,
and action evidence — with binding checks, persistence-failure signaling, and
cross-process resume guidance. `#786` task-context is an explicit dependency
state (`UNAVAILABLE` until present on the stack).

## Documents

| Doc | Role |
|---|---|
| [VALIDATION-CYCLE-788.md](./VALIDATION-CYCLE-788.md) | What Formal IV vs tip CI covers |
| [A2-006-EVIDENCE.md](./A2-006-EVIDENCE.md) | Candidate identities |
| [ATLAS-DOC-RECEIPT.md](./ATLAS-DOC-RECEIPT.md) | Doc receipt |

## CLI

```bash
atlas-studio mission-session --intent-file intent.json --decision-file decision.json --json
atlas-studio session --intent-file intent.json --persistence-failed-after-mutation
```

## Honesty

```text
SESSION != AUTHORITY
AUTO_RETRY = FORBIDDEN
MISMATCHED_BINDING != SUCCESS
PERSISTENCE_FAILED != CONFIRMED_SUCCESS
FORMAL_IV_TIP != LATER_TIP
TASK_CONTEXT dependency = explicit UNAVAILABLE|AVAILABLE
```
