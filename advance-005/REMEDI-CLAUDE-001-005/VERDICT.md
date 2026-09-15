# REMEDI-CLAUDE-001-005 — Group B freshness/conflict hotfix

| Field | Value |
|---|---|
| Worker | REMEDIATOR |
| Base | `origin/main` @ `b0d4413` |
| Branch | `hotfix/adv005-claude-001-005-freshness` |
| Surface | `src/project_atlas/runtime_22.py` |

## Disposition summary

| ID | Pre-remedi | Post-remedi | Fix |
|---|---|---|---|
| CLAUDE-ADV005-001 | REPRODUCED (CRIT) | **REFUTED** | Conservative multi-provenance freshness aggregation |
| CLAUDE-ADV005-005 | REPRODUCED (HIGH) | **REFUTED** | Order-independent stale-wins merge |
| CLAUDE-ADV005-012 | REPRODUCED (MED) | **REFUTED** | `excluded_conflicts_detail` + `excluded_conflict_ids` in receipt |

## Minimal changes

1. `_aggregate_portfolio_freshness` — collect all portfolio hits; return most conservative label (`stale` > `unknown` > `fresh`).
2. Conflict exclude path — retain bounded conflict metadata in `pipeline_receipt` when entries are dropped.

## Evidence

- `probe_freshness.py` / `probe-result.json` / `probe-run.txt`

## Gates

| Gate | Status |
|---|---|
| FRESHNESS | PASS |
| CONFLICTS | PASS |
| DETERMINISM (freshness order) | PASS |
| pytest `test_as_2_2_runtime_001.py` | PASS (21/21) |
