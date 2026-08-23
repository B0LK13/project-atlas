# AS-ORCH-INTEGRATION-IV-001B — Independent IV for AS-ORCH-001B

**Package:** AS-ORCH-INTEGRATION-IV-001B  
**Backlog:** ORCH001B-008  
**Target implementation:** AS-ORCH-001B (`atlas orchestrator route-result`)  
**LIVE_MAIN_HEAD:** `4e71cce0d1c97f408347e256300a41590da4c352`

## What was verified

Independent integration verification exercises the real CLI chain via subprocess
(`python -m project_atlas.cli orchestrator route-result`) against untrusted
`AgentResultEnvelope` JSON:

| Case | Scenario | Expected behavior |
|------|----------|-------------------|
| A | Valid `PASS` + `CERTIFIED` | `route_kind=task`, `INTEGRATION_VERIFY`; `execution_authorized=false` |
| B | `MERGE_ELIGIBLE` + requested `MERGE` | `owner_gate`; `OWNER_REQUIRED`; never `MERGE` |
| C | Malformed JSON / extra `execution_authorized` | Fail-closed `REJECTED` |
| D | `BLOCKED` outcome | `route_kind=terminal`; no authority |
| E | Repeated route of the same envelope | Identical JSON |

## Honesty

- **Routing != dispatch.** A task route may be `dispatchable=true` as policy
  metadata; `execution_authorized` remains `false`.
- **IV != merge authorization.**
- **`dispatchable` != `execution_authorized`.**

## Commands run

```bash
.venv/bin/python -m ruff check tests/integration/test_orchestration_iv_001b.py
.venv/bin/python -m pytest tests/integration/test_orchestration_iv_001b.py -v --no-cov
```

### Results

```
ruff: All checks passed
pytest: 5 passed
```
