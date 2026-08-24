# AS-ORCH-INTEGRATION-IV-001C — Independent IV for AS-ORCH-001C

**Package:** AS-ORCH-INTEGRATION-IV-001C  
**Backlog:** ORCH001C-009  
**Target implementation:** `atlas orchestrator cursor-stage-result` + `cursor-complete`  
**LIVE_MAIN_HEAD:** `4e71cce0d1c97f408347e256300a41590da4c352`

## What was verified

CLI chain (subprocess) on a temp `--root`:

| Case | Scenario | Expected |
|------|----------|----------|
| A | Valid PASS staged then completed | `HANDOFF_READY` / explicit / no authority |
| B | MERGE_ELIGIBLE | `OWNER_REQUIRED` |
| C | Tampered staged merge permission | fail-closed non-zero |
| D | Missing receipt | `TERMINAL` |
| E | `cursor-status` | never authorizes execution |

## Honesty

- Handoff != dispatch.
- Acknowledgement / completion != authority.
- Authentic Cursor stop-event delivery remains ENVIRONMENT_DEPENDENT (ORCH001C-010).

## Results

```
pytest tests/integration/test_orchestration_iv_001c.py -v --no-cov
5 passed
ruff: All checks passed
```
