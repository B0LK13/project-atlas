# AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001

**Directive:** D-128-PERSISTENT-GOVERNOR-NONBLOCKING-SCHEDULER-LIVENESS-001  
**Package:** `AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001`  
**Parent:** D-127 (PR430 merged + autonomous DAG continuation)  
**Merge authorization:** `NOT_GRANTED` (draft; owner gate at end)

## Problem

The persistent Atlas governor must not treat pending CI / workers / Cloud runs as a
**global** scheduler block. Waiting is a **node** state, not a governor state.

## Invariant

```
PENDING_EXTERNAL_EVENT != GLOBAL_SCHEDULER_BLOCK
```

## Architecture

### Durable external observers

Module: `project_atlas.orchestration.sdk.external_observers`

Each external wait is a durable observer:

| Field | Role |
|---|---|
| `observer_id` | Stable identity |
| `observer_type` | `GITHUB_CI` / `CURSOR_CLOUD_RUN` / `LOCAL_WORKER` / `REMOTE_SMOKE` / `RETRY_TIMER` |
| `package_id` / `generation` | Package binding |
| `external_id` | Run id / agent id / timer id |
| `expected_head` / `expected_tree` | Exact-pin binding |
| `next_poll_at` | Bounded wake |
| `status` | `PENDING` / `RUNNING` / `TERMINAL_*` / `PARKED` / `CANCELLED` |

Observers have **no** merge authority (`merge_authorized=False` always).

### Nonblocking scheduler tick

Module: `project_atlas.orchestration.sdk.nonblocking_scheduler`

Each tick:

1. Reconcile due observers (poll snapshots only — never `wait_until_terminal`)
2. Idempotently consume terminal events
3. Detect / self-reconcile stalls (`READY>0` + `PENDING_EXTERNAL>0` + no progress)
4. Dispatch READY work **even while** externals are pending
5. Persist liveness (`scheduler-liveness.json`)

Sleep only until `min(next_poll_at)` capped by `BOUNDED_IDLE_CAP_SEC` / supervisor poll interval.

### Scheduler ingest fix (B-class removal)

`DagToAgentScheduler.ingest_completions`:

- Polls `get_run_status`
- Finalizes with `wait_run` **only** when already terminal
- Nonterminal runs stay observed; cycle continues
- `AGENT_BUSY` parks with backoff (`RESOURCE_YIELD != OWNER_REQUIRED`) — no cycle-blocking `wait_run`

## Live proof (PR431 + PR432)

While CI `32498760059` (PR431) and `32498766361` (PR432) are running, the governor:

1. Registers durable CI observers for both
2. Dispatches independent D-128 READY work / verification
3. Continues the DAG without waiting for either CI to finish

Required evidence:

- `EXTERNAL_WAIT_COUNT >= 2`
- `READY_WORK_DISPATCHED_WHILE_WAITING >= 1`
- `TWO_RUNNING_CI_JOBS_DO_NOT_BLOCK_DISPATCH = PASS`

## Owner / merge policy

- This package uses speculative certification (`AS-ORCH-SPECULATIVE-CERTIFICATION-001`)
- Freezes to `OWNER_HELD_MERGE_ELIGIBLE` on success
- **Does not** auto-merge; future merge authorization remains `NOT_GRANTED`
- Does **not** mutate PR431 / PR432 feature surfaces

## Success targets

- `GLOBAL_BLOCKING_CI_WAIT_COUNT = 0`
- `GLOBAL_BLOCKING_WORKER_WAIT_COUNT = 0`
- `OWNER_HELD_PACKAGE_CAUSES_GLOBAL_STOP = NO`
- `RESOURCE_YIELD_CAUSES_OWNER_REQUIRED = NO`
- `DUPLICATE_EVENT_CONSUMPTION = 0`
- `OUTER_SHELL_REQUIRED_FOR_PROGRESS = NO` (durable observers reconstruct after restart)
