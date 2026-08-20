# AS-ORCH-CONTINUATION-BROKER-001

_Status: **IMPLEMENTED — NOT CERTIFIED**. Control-plane reliability supervisor. Does **not** merge, grant owner authority, expand objectives, or become a second governor._

## Purpose

Bridge the gap between the landed AS-ORCH-001E persistent logical loop and
`SESSION_ONE_SHOT` execution transport so a nonterminal checkpoint starts
exactly one successor cycle without using the human owner as scheduler.

## Continuation backend

```
CONTINUATION_BACKEND_SELECTED =
SAME_PROCESS_SUPERVISOR_OVER_001E_WITH_001D_DISPATCHPORT

CONTINUATION_BACKEND_EVIDENCE =
src/project_atlas/orchestration/autonomy/broker.py
+ src/project_atlas/orchestration/autonomy/loop.py
+ src/project_atlas/orchestration/dispatcher.py
+ atlas orchestrator governor-broker-run
+ atlas orchestrator dispatch-once / dispatch-recover
```

No Cursor API, webhook, GitHub Actions scheduler, or new credential is invented.

## Ownership

The broker owns only:

- invocation lifecycle
- successor cycle start
- result re-ingestion
- duplicate checkpoint suppression
- owner-request deduplication
- `WAITING_OWNER` park / resume after a genuine external owner transition

001E remains the logical continuation engine. 001D remains the dispatch primitive.

## Honesty

- `BROKER_IS_SECOND_GOVERNOR = NO`
- `BROKER_CAN_AUTHORIZE_MERGE = NO`
- `BROKER_CAN_BYPASS_OWNER_GATE = NO`
- `BROKER_CAN_EXPAND_OBJECTIVE = NO`
- `WORKER_TERMINAL != DAG_TERMINAL`
- `RESOURCE_BOUNDARY` with remaining safe work is an internal yield
- `OWNER_PROMPT_BUDGET = 1` per unchanged fingerprint
- Seeded request `BATCH-B-CONTEXT-INTEGRATION-001` is already issued
- `MERGE_AUTHORIZATION = NOT_GRANTED`

## CLI

```bash
atlas orchestrator governor-broker-run --root <repo>
```
