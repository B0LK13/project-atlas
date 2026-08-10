# AS-2.1-WEB-LIVE-001

Web shell prefers LIVE_API (`VITE_ATLAS_API_BASE`, default `http://127.0.0.1:8765`)
via `/v1/snapshot`, then falls back to an **isolated demo stub** at
`/sample-read-status.json` when LIVE_API is unreachable.

## Demo isolation

| Flag / field | Meaning |
|---|---|
| `VITE_ATLAS_DEMO_ONLY=1` | Force demo stub; never call LIVE_API |
| `data_source=demo_stub` | Sample/demo path (not live vault) |
| `data_source=live_api` | Live read projection |
| `demo_isolated=true` | Stub path cannot be relabelled as live |

Invariants: UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy · demo ≠ LIVE.
