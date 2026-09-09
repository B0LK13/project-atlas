# AS-STUDIO-A2-005 — Intent Continuity

```text
AS_STUDIO_A2_005                   = IMPLEMENTED_IN_LANE
BASE                               = A2-004 stack (same branch PR #788)
MUTATION                           = NONE
AUTO_RETRY                         = FORBIDDEN
FORMAL_IV                          = NOT_STARTED
MERGE_AUTHORIZATION                = NOT_GRANTED
```

Read-only inspect for interrupted sessions, stale intents, and duplicate-submit
risk after a prior decision. Complements `action-evidence`.

## CLI

```bash
atlas-studio intent-continuity --intent-file intent.json --json
atlas-studio continuity --intent-file intent.json --decision-file decision.json
```

## Honesty

```text
STALE_INTENT != PERMISSION
DUPLICATE_SUBMIT_RISK != AUTO_RETRY
INSPECT != EXECUTE
AUTO_RETRY = FORBIDDEN
```
