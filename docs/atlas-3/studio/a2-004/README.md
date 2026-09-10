# AS-STUDIO-A2-004 — Action Evidence & Recovery

```text
AS_STUDIO_A2_004                   = IMPLEMENTED_IN_LANE
BASE                               = A2-002 tip (explicit stack; certified A2 preserved)
MUTATION                           = NONE (inspect + optional non-canonical spool)
AUTO_RETRY                         = FORBIDDEN
FORMAL_IV                          = NOT_STARTED
MERGE_AUTHORIZATION                = NOT_GRANTED
```

Read-only projection that inspects an `ATLAS_STUDIO_ACTION_DECISION_V1`
packet, classifies outcomes for Mission Control / Development Plane users,
and emits recovery guidance that **never auto-retries** mutations.
Optional spool write feeds the governed knowledge-capture path as
non-canonical evidence only (`CAPTURE != AUTHORITY`).

## Documents

| Doc | Role |
|---|---|
| [A2-004-FIRST-WORK-PACKAGE.md](./A2-004-FIRST-WORK-PACKAGE.md) | Scope, acceptance, non-goals |
| [A2-004-EVIDENCE.md](./A2-004-EVIDENCE.md) | Candidate identity + validation |
| [ATLAS-DOC-RECEIPT.md](./ATLAS-DOC-RECEIPT.md) | Doc receipt |

## CLI

```bash
atlas-studio action-evidence --decision-file decision.json --json
atlas-studio evidence --decision-file decision.json --write-spool --spool-dir .tmp/spool
```

## Honesty

```text
STUDIO_UI != AUTHORITY
EXECUTION_FAILURE != SUCCESS
UNCERTAIN_MUTATION != NOTHING_CHANGED
AUTO_RETRY = FORBIDDEN
MONITOR != RE-EXECUTE
CAPTURE != AUTHORITY
SPOOL != TRUTH_CORE
CI_PASS != FORMAL_IV
```
