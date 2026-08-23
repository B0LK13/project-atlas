# AS-ORCH-INTEGRATION-IV-001A — Independent IV for AS-ORCH-001A

**Package:** AS-ORCH-INTEGRATION-IV-001A  
**Backlog:** ORCH001A-007  
**Target implementation:** AS-ORCH-001A (`atlas orchestrator validate-result`)  
**LIVE_MAIN_HEAD:** `4e71cce0d1c97f408347e256300a41590da4c352`

## What was verified

Independent integration verification exercises the real CLI chain via subprocess
(`python -m project_atlas.cli orchestrator validate-result`) against untrusted
`AgentResultEnvelope` JSON:

| Case | Scenario | Expected behavior |
|------|----------|-------------------|
| A | Valid `PASS` + `CERTIFIED` local envelope | Classified to `INTEGRATION_VERIFY` / `LOCAL_ACCEPTED`; no authority granted |
| B | `MERGE_ELIGIBLE` with requested `MERGE` | `OWNER_REQUIRED`; never `MERGE`; no execution |
| C | Malformed JSON and schema-tampered envelope (`execution_authorized`) | Fail-closed non-zero exit; `REJECTED` |
| D | Terminal / owner-gate outcomes (`BLOCKED`, `OWNER_REQUIRED`, `RECERTIFY_REQUIRED`, `REMEDIATION_REQUIRED`, `BLOCKED_UNKNOWN_STATE`) | Non-dispatch transitions; no authority |
| E | Repeated validate of the same valid envelope | Byte-stable JSON decision output |

## Honesty

- **IV != merge authorization** — integration verification classifies envelopes only; it does not merge, dispatch, or grant owner authority.
- **Classification != execution** — `execution_authorized` and `merge_authorized` remain `false` on every path exercised.
- **PASS != MERGE AUTHORIZATION** — `MERGE_ELIGIBLE` routes to `OWNER_REQUIRED`, never `MERGE`.
- **PROMOTE_ELIGIBLE != MERGED/DEPLOYED/AUTHORITATIVE**

## Commands run

```bash
.venv/bin/python -m ruff check tests/integration/test_orchestration_iv_001a.py
.venv/bin/python -m pytest tests/integration/test_orchestration_iv_001a.py -v
```

### Results

```
$ .venv/bin/python -m ruff check tests/integration/test_orchestration_iv_001a.py
All checks passed!

$ .venv/bin/python -m pytest tests/integration/test_orchestration_iv_001a.py -v
============================== 5 passed in 16.07s ==============================
```

Tests: `test_iv_001a_a_valid_pass_envelope_classified_without_authority`,
`test_iv_001a_b_merge_eligible_never_merge_never_execution`,
`test_iv_001a_c_tampered_and_invalid_fail_closed`,
`test_iv_001a_d_terminal_and_owner_gate_outcomes_stay_non_dispatch`,
`test_iv_001a_e_idempotent_revalidate_is_stable`.
