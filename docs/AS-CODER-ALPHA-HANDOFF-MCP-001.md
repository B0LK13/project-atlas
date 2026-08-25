# AS-CODER-ALPHA-HANDOFF-MCP-001 — vault-scoped handoff read

Package ID: `AS-CODER-ALPHA-HANDOFF-MCP-001`.

Read-only inventory of durable Coder Alpha handoff packs already written by
`atlas handoff create`. Agents and Web can see what is resumable without
re-explaining the project.

## Surfaces

- MCP: zero-arg `atlas.handoff.read`
- LIVE_API: `GET /v1/handoffs` (optional `?project=`)
- Web: `#/handoffs` (optional `?project=`)

## Honesty

- `HANDOFF != AUTHORITY`
- `MCP != WRITE`
- `UI != CANONICAL`
- Empty inventory is UNKNOWN, not a healthy zero
- This package does not create, resume, or rewrite packs
- No request args on MCP; project filter is LIVE_API/Web only
- `AUTHENTIC_PILOT = NO` unless a later owner-bound run proves otherwise

## Non-goals

- D-149 owner-gate remediation (remains draft `#483`)
- Authentic O2 (`AUTHENTIC_ESTATE_ROOT` unset)
- Merge authorization
