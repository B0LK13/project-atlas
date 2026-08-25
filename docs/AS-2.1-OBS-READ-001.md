# AS-2.1-OBS-READ-001 — Read-only observability compute

Package ID: `AS-2.1-OBS-READ-001`.

`GET /v1/obs` previously persisted `generated/ops/obs/*-live.json` on every
read. That made a LIVE_API GET a vault write and blocked a read-only MCP wrap.

## Contract

| Helper | Role |
|---|---|
| `compute_live_observability_receipt()` | Presence/lane snapshot; **no write** |
| `build_live_observability_receipt()` | Explicit persist of the same payload |

Read surfaces use compute only:

- LIVE_API `GET /v1/obs`
- MCP `atlas.obs.read`

`obs_perf` and other explicit ops persist paths still call `build_*`.

## Honesty

- Rollup remains `unknown` (presence ≠ healthy)
- `authority_plane = none`
- OBS ≠ project authority
- MCP remains zero-arg and write-free
