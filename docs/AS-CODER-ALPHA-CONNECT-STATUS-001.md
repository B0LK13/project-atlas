# AS-CODER-ALPHA-CONNECT-STATUS-001 — Connect status lens

Vault-scoped read of the last `atlas connect` artifacts so humans and agents
can see whether a vault was bound without re-running compile.

Package ID: `AS-CODER-ALPHA-CONNECT-STATUS-001`.

## Surfaces

- CLI: `atlas connect-status --vault <dir> [--json]`
- LIVE_API: `GET /v1/connect-status` (zero-arg, vault-scoped)
- Web: `#/connect`
- MCP: `atlas.connect.status.read` (zero-arg vault-read)

## Honesty

- `CONNECT_STATUS != AUTHORITY`
- `UNKNOWN != FRESH` — missing or unreadable receipts stay UNKNOWN
- `SKIP != TRUTH CORE` — incremental no-change skip is operational only
- `OWNER_CAPABILITY_GRANTED = false`
- `AUTHENTIC_PILOT = false`
- Demo stub does not fabricate a bound vault

This package does not mutate DAG/owner gates, does not consume
`AUTHENTIC_ESTATE_ROOT`, and does not grant merge.
