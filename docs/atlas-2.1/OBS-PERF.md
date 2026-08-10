# AS-2.1-OBS-PERF-001 — Observability / performance deepen

**Package:** `AS-2.1-OBS-PERF-001`  
**Plane:** operational only (≠ authority, ≠ Layer B, ≠ release gate)  
**Tip base:** `f45134f` / TREE `02eeb7392a7cfcbf78a8c28a2034cf0b54ac509e`

## Intent

Close remaining **fixture-scale** visibility gaps for live read lanes:

| Lane | Observability | Perf baseline measurement |
|---|---|---|
| API | `lanes.api` in obs receipt | `api_health_read_ms`, `api_projects_read_ms` |
| MCP | `lanes.mcp` | `mcp_list_tools_ms`, `mcp_invoke_health_ms` |
| Query | `lanes.query` (Ask + plan) | `ask_atlas_query_ms`, `query_plan_build_ms` |
| Sync | `lanes.sync` (dry-run only) | `sync_plan_dry_run_ms` |

## Owned surfaces

- `src/project_atlas/obs_live.py` (lane visibility deepen)
- `src/project_atlas/perf_baselines.py` (lane timings deepen)
- `src/project_atlas/obs_perf.py` (combined deepen receipt)
- `docs/atlas-2.1/OBS-PERF.md` (this guide)
- `tests/unit/test_as_2_1_obs_perf_001.py`

## Explicit non-ownership

- No edits to shared JSON schemas / `schema.py`
- No dual-own of `api_server.py`, `authz.py`, `ops_receipts.py`, `autonomy_l3.py`, Web Mission/Workspace pages
- Sync timings use **dry-run scaffold** only — never invent authentic estate PILOT
- `rollup` remains `unknown` (Unknown ≠ healthy)
- Perf receipts are **not** release gates and do not substitute authentic PILOT

## Operator usage

```bash
# Existing CLI (deepened measurements written under generated/ops/perf/)
atlas live perf-baseline --vault <vault> --baseline-id obs-perf-lanes --iterations 2 --json

# Library combined receipt (tests / scripts)
python -c "from pathlib import Path; from project_atlas.obs_perf import build_obs_perf_receipt; \
print(build_obs_perf_receipt(Path('<vault>'))['package_id'])"
```

## Truth boundary

`OBS-PERF DEEPEN != AUTHORITY / != RELEASE GATE / != AUTHENTIC PILOT / UNKNOWN!=HEALTHY`
