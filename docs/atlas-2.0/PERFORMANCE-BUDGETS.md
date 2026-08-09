# PREP — Performance budgets (fixture-scale)

Status: **PREP ONLY**. Not production SLOs. Aligns with ADV `perf_budget_smoke`
objective counters (file/byte/op counts — prefer deterministic signals).

## Fixture budgets (design intent)

| Pipeline step | Soft budget signal | Hard fail? |
|---|---|---|
| discover (fixture corpus) | file count bounded by fixture inventory | fixture tests only |
| ingest | ops counted; no wall-clock hard fail in CI | soft advisory |
| build-indexes | stable-plane byte digest comparable | yes (determinism) |
| validate | findings countable | severity exits per H-010 |
| adv certify matrix | case list complete; `release_certified=false` | N/A |

## 2.0 planning note

Federation/sync v2 budgets deferred until estate PILOT exists. Do not invent
load numbers from missing roots.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.
