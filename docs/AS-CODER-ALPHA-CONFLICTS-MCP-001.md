# AS-CODER-ALPHA-CONFLICTS-MCP-001 — vault-scoped conflict index

Zero-arg, vault-scoped unresolved conflict projection for LIVE_API, MCP, and Web.

Package ID: `AS-CODER-ALPHA-CONFLICTS-MCP-001`.

## What this is

- `GET /v1/conflicts` without `project` returns the vault-scoped index.
- `GET /v1/conflicts?project=<id>` remains the existing project-scoped projection.
- MCP tool `atlas.conflicts.read` is zero-arg (`{"tool":"..."}` only).
- Web `#/conflicts` consumes the vault-scoped index.

## Honesty

- Conflict projection ≠ authority
- Conflict projection ≠ resolution (no winner is selected)
- UNKNOWN is valid
- MCP / UI ≠ canonical
- `owner_capability_granted` is hardcoded false
- A readable authentic estate does not grant owner authority
- Vault-scoped ≠ implicit portfolio-all
- No request-arg protocol; extra MCP keys fail closed

## Out of scope

- D-149 owner-gate remediation (stays on draft #483)
- Authentic O2 / `AUTHENTIC_ESTATE_ROOT`
- Merge authorization
- Ask2 / kdiff request-arg protocol
