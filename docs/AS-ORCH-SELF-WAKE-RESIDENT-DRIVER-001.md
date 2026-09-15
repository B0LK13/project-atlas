# AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001

Closes the D-130 autonomy gap: the primary Atlas CLI governor owns its own
next scheduler tick.

```
RESIDENT DRIVER -> PRIMARY GOVERNOR TICK -> DURABLE DAG -> DISPOSABLE WORKERS
```

## Invariants

- `EXTERNAL_TRIGGER_REQUIRED_FOR_NEXT_SCHEDULER_TICK = NO`
- `FOLLOWUP_MESSAGE_REQUIRED_FOR_NORMAL_PROGRESS = NO`
- `OUTER_SESSION_EXIT_STOPS_DAG = NO`
- `FUTURE_AUTO_MERGE = NO`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

## Stacking

- `STACKED_DEPENDENCY = PR433`
- `MERGE_ORDER = PR433 -> SELF_WAKE_DRIVER`
- Does not mutate frozen PR433 tip content beyond stacking base.

## Surfaces

- `resident_mission.py` — standing mission survives restart
- `resident_status.py` — observability status file
- `resident_driver.py` — self-wake loop + CI poll + READY override sleep
- `resident_windows.py` — DETACHED_PROCESS + optional logon Scheduled Task
- CLI: `atlas orchestrator governor-resident-run`

## Not rewritten

DAG authority, worker authority, speculative certification, continuation
broker, and lease engine remain as-is unless a demonstrated defect requires
narrow change.
