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

## 2.1 OBS-PERF local baselines (AS-2.1-OBS-PERF-001)

Fixture-scale `duration_ms` samples only — **not** production SLOs and **not**
a release gate. See `docs/atlas-2.1/OBS-PERF.md`.

| Lane | Measurement keys | Soft advisory |
|---|---|---|
| API (AppService reads) | `api_health_read_ms`, `api_projects_read_ms` | record only |
| MCP | `mcp_list_tools_ms`, `mcp_invoke_health_ms` | record only |
| Query | `ask_atlas_query_ms`, `query_plan_build_ms` | record only |
| Sync dry-run | `sync_plan_dry_run_ms` | scaffold only; ≠ authentic SYNC |

Hard fail in CI is limited to harness correctness (schema of receipt, fail-closed
iteration bounds). Wall-clock thresholds are never release-blocking.
