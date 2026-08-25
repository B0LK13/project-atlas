# AS-CODER-ALPHA-INDEX-STATUS-001 — Index status lens

Vault-scoped read of existing lexical indexes so humans and agents can see
whether retrieval artifacts are present without running `atlas build-indexes`
or inventing a query.

Package ID: `AS-CODER-ALPHA-INDEX-STATUS-001`.

## Surfaces

- CLI: `atlas index-status --vault <dir> [--json]`
- LIVE_API: `GET /v1/index-status` (zero-arg, vault-scoped)
- Web: `#/indexes`
- MCP: `atlas.indexes.status.read` (zero-arg vault-read)

## Honesty

- `INDEX_STATUS != AUTHORITY`
- `UNKNOWN != HEALTHY` — missing or unreadable indexes stay UNKNOWN
- `PRESENCE != VALIDATE` — recorded files are not a Core validate pass
- `PRESENCE != FRESH` — presence is not currentness
- Obsolete `indexes/` is never treated as the generated contract
- `OWNER_CAPABILITY_GRANTED = false`
- `AUTHENTIC_PILOT = false`
- Demo stub does not fabricate a recorded index inventory

This package does not mutate DAG/owner gates, does not consume
`AUTHENTIC_ESTATE_ROOT`, and does not grant merge.
