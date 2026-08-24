# AS-ORCH-INTEGRATION-IV-001D — Independent IV for owner/terminal non-dispatch

**Package:** AS-ORCH-INTEGRATION-IV-001D  
**Backlog:** ORCH001D-011 (partial: owner/terminal non-start; not authentic Windows dispatch)  
**LIVE_MAIN_HEAD:** `4e71cce0d1c97f408347e256300a41590da4c352`

## What was verified

CLI chain on a temp `--root`:

| Case | Scenario | Expected |
|------|----------|----------|
| A | `dispatch-status` with no dispatch | no execution/merge/process |
| B | MERGE_ELIGIBLE → `dispatch-once` | `process_started=false` |
| C | TERMINAL (no receipt) → `dispatch-once` | `process_started=false` |
| D | Missing handoff → `dispatch-once` | fail-closed, no process |

This IV does **not** start a real agent for a HANDOFF_READY task.

## Honesty

- `PROCESS_STARTED = NO` on owner/terminal/missing-handoff.
- Authentic Windows Cursor dispatch (ORCH001D-012) remains EXTERNAL/OWNER.
- IV != merge authorization.

## Results

```
pytest tests/integration/test_orchestration_iv_001d.py -v --no-cov
4 passed
```
