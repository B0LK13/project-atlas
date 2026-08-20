# AS-ORCH-CONTINUATION-BROKER-001

_Status: **IMPLEMENTED — NOT CERTIFIED**. Control-plane reliability supervisor plus
durable host and governed mutating worker port. Does **not** merge, grant owner
authority, expand objectives, or become a second governor._

## Purpose

Bridge the gap between the landed AS-ORCH-001E persistent logical loop and
`SESSION_ONE_SHOT` execution transport so a nonterminal checkpoint starts
exactly one successor cycle without using the human owner as scheduler.

D-080 adds the missing outer-host facts:

- the broker process itself must be supervised by a durable host
- `run()` resource-boundary is an internal yield, not process exit
- 001D Ask-mode stays the read-only verification transport
- mutating implementation uses a distinct `MutatingExecutionPort`

## Architecture

```
DURABLE HOST SUPERVISOR
        │
        ▼
AS-ORCH-CONTINUATION-BROKER-001
        │
        ▼
PRIMARY GOVERNOR / DAG
        │
        ├───────────────┐
        ▼               ▼
READ-ONLY PORT      MUTATING WORKER PORT
001D Ask/IV         governed implementation
        │               │
        ▼               ▼
Cursor Ask          Cloud Agents API v1
verification        or local Agent/ACP
        │               │  or process backend
        └───────┬───────┘
                ▼
         RESULT REGISTRY
                │
                ▼
          NEXT DAG CYCLE
```

Only one primary governor exists.

## Continuation backend

```
CONTINUATION_BACKEND_SELECTED =
DURABLE_HOST_SUPERVISOR_OVER_001E_WITH_001D_ASK_AND_MUTATING_PORT

CONTINUATION_BACKEND_EVIDENCE =
src/project_atlas/orchestration/autonomy/broker.py
+ src/project_atlas/orchestration/autonomy/host_service.py
+ src/project_atlas/orchestration/autonomy/mutating_transport.py
+ src/project_atlas/orchestration/autonomy/cursor_cloud.py
+ src/project_atlas/orchestration/autonomy/local_agent.py
+ atlas orchestrator governor-service-run
+ atlas orchestrator governor-broker-run
+ atlas orchestrator dispatch-once / dispatch-recover
```

001D `READ_ONLY_CURSOR_FLAGS` remain Ask-mode. They are not weakened.

## Mutating port

`MutatingExecutionPort` consumes an existing package-scoped lease. It never
grants one. Required bindings: package ready, valid lease, exact base main,
exact repository, role IMPLEMENTER|REMEDIATOR, allowed paths, governed
branch/worktree, `merge_authorized=False`, `direct_main=False`.

Preferred backend when `CURSOR_API_KEY` is present: documented Cursor Cloud
Agents API v1 (`POST/GET /v1/agents`, `POST/GET /v1/agents/{id}/runs`).
`409 agent_id_conflict` and `409 agent_busy` recover the existing worker.
No invented endpoints. API keys are never persisted or printed.

Fallback: authenticated local Cursor Agent/ACP (not Ask mode). If neither
authentic backend is available, the durable host may use a real OS-process
worker for host-lifetime proof and emit one deduplicated prerequisite
`AUTHENTIC-MUTATING-BACKEND-001`.

## Durable host

```bash
atlas orchestrator governor-service-run --root <repo>
atlas orchestrator governor-service-stop --root <repo>
atlas orchestrator governor-service-install --root <repo>
```

`governor-service-run` returns only on explicit stop, safety stop, or
unrecoverable host failure. `WAITING_OWNER` parks. Resource-boundary loops
internally.

Linux: `scripts/linux/install-project-atlas-governor.sh` (systemd --user).
Windows: `scripts/windows/Install-ProjectAtlasGovernor.ps1` (task
`ProjectAtlasGovernor`). Neither embeds secrets.

## Honesty

- `BROKER_IS_SECOND_GOVERNOR = NO`
- `BROKER_CAN_AUTHORIZE_MERGE = NO`
- `BROKER_CAN_BYPASS_OWNER_GATE = NO`
- `WORKER_TERMINAL != DAG_TERMINAL`
- `RESOURCE_BOUNDARY` with remaining safe work is an internal yield
- `OWNER_PROMPT_BUDGET = 1` per unchanged fingerprint
- Seeded request `BATCH-B-CONTEXT-INTEGRATION-001` is already issued
- `MERGE_AUTHORIZATION = NOT_GRANTED`
- `HANDS_OFF_DEVELOPMENT_AFTER_OUTER_CURSOR_SESSION_EXIT` is proven only
  after real host-lifetime + worker-backend + independent IV/ADV
- `BROKER_CERTIFICATION = NOT_GRANTED` until those gates pass

## CLI (bounded in-process supervisor remains)

```bash
atlas orchestrator governor-broker-run --root <repo>
```
