# AS-2.1-WEB-LIVE-001

Web shell prefers LIVE_API (`VITE_ATLAS_API_BASE`, default `http://127.0.0.1:8765`)
via `/v1/snapshot`, then falls back to an **isolated demo stub** at
`/sample-read-status.json` when LIVE_API is unreachable.

## SEC-009 session auth (local demo)

After `#264`, LIVE_API requires a high-entropy **per-launch** Bearer credential.
`atlas live api-serve` prints `ATLAS_API_READ_TOKEN=…` once on stderr.

For the Windows productization path, `scripts/windows/atlas-start.ps1`:

1. Captures that READ token from api-serve stderr (value never logged to the console).
2. Sets `VITE_ATLAS_API_TOKEN` for the Vite child process (READ only — not the privileged token).
3. Optionally writes the token under `.tmp/productization/state/` with a restrictive ACL (runtime state, **not** the repo).

Web hooks call `apps/web/src/api/liveApi.ts` (`liveApiFetch`), which sends
`Authorization: Bearer ${VITE_ATLAS_API_TOKEN}` and fails closed with an honest
error when the token is missing. Tokens are never placed in URL/query strings,
never hardcoded, and auth is never disabled.

## Demo isolation

| Flag / field | Meaning |
|---|---|
| `VITE_ATLAS_DEMO_ONLY=1` | Force demo stub; never call LIVE_API |
| `VITE_ATLAS_API_TOKEN` | Per-launch READ Bearer (local-only; set by atlas-start) |
| `data_source=demo_stub` | Sample/demo path (not live vault) |
| `data_source=live_api` | Live read projection |
| `demo_isolated=true` | Stub path cannot be relabelled as live |

Invariants: UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy · demo ≠ LIVE.
