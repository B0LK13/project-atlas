# AS-CODER-ALPHA-SNAPSHOT-MCP-001 — vault-scoped facade snapshot

Zero-arg MCP + Web consume of the existing LIVE_API `GET /v1/snapshot` facade.

Package ID: `AS-CODER-ALPHA-SNAPSHOT-MCP-001`.

## What this is

- MCP tool `atlas.snapshot.read` is zero-arg (`{"tool":"..."}` only).
- Web `#/snapshot` reads `GET /v1/snapshot`.
- Existing `/v1/snapshot` payload is unchanged.

## What this is not

- Not `atlas snapshot` / `atlas restore` backup bundles
- Not owner capability
- Not authentic PILOT
- Not Layer B authority

## Honesty

- Facade snapshot ≠ backup bundle
- MCP / UI ≠ canonical
- Graph ≠ authority
- `owner_capability_granted` is hardcoded false
