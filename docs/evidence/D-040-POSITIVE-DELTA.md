# D-040 — CHANGED-002 positive-delta proof

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-040
**Package:** AS-CODER-ALPHA-CHANGED-002 (positive delta)

## Scenario

```
BASELINE CONNECT
  → add NEW.md, modify README.md, remove GONE.md
  → create .atlas-vault/noise.md (operational churn)
SECOND CONNECT
```

## Executable proof

Unit test: `tests/unit/test_as_coder_alpha_changed_001.py::test_second_connect_reports_removed_and_self_churn_not_dominating`

Observed:

| Signal | Result |
|---|---|
| ADDED SOURCE | `NEW.md` |
| MODIFIED SOURCE | `README.md` |
| REMOVED SOURCE | `GONE.md` |
| rollup | `changed` |
| `.atlas-vault/` noise in delta | absent (excluded) |

## Metrics

```
MEANINGFUL_CHANGES_RECALL = 3/3 (add+mod+remove)
FALSE_POSITIVE_CHANGE_COUNT = 0 (.atlas-vault noise not counted)
MISSED_CHANGE_COUNT = 0
ATLAS_SELF_CHURN_COUNT = 0
```

## Non-claims

```
DEMO_FIXTURE != AUTHENTIC_PILOT
DEMO != RELEASE
UI != CANONICAL_TRUTH
MODEL_OUTPUT != AUTHORITY
CODEX_VALIDATED = NO
EXTERNAL_SECURITY_REVALIDATION_REQUIRED = YES
ATLAS_OPT_WAKE_GATE = CLOSED
```
