# AS-CODER-ALPHA-LENS-MCP-001

Vault-scoped, zero-arg MCP tools for the existing Coder Alpha lenses:

| Tool | Package | Lens |
|---|---|---|
| `atlas.overview.read` | `AS-CODER-ALPHA-OVERVIEW-MCP-001` | What is this project? |
| `atlas.decisions.read` | `AS-CODER-ALPHA-DECISIONS-MCP-001` | What decisions matter? |
| `atlas.unknown.read` | `AS-CODER-ALPHA-UNKNOWN-MCP-001` | What is unknown / conflicting? |
| `atlas.changed.read` | `AS-CODER-ALPHA-CHANGED-MCP-001` | What changed? |

## What this is

Read-only MCP dispatch over the same library builders the CLI uses
(`build_overview_lens`, `build_decisions_lens`, `build_unknown_lens`,
`build_changed_lens`). Requests remain `{ "tool": "..." }` only.

## What this is not

- Authority, merge authorization, or owner-capability grant
- A write / materialize path (`generated/answers` is not created)
- Inventory rotation (`connect-inventory.json` is never rewritten)
- Conflict resolution or review promotion
- A request-arg / project-selector surface
- Authentic pilot certification

## Honesty

```
MCP LENS != AUTHORITY
UNKNOWN VALID
NO WRITE
VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL
NO INVENTORY ROTATE
OWNER_CAPABILITY_GRANTED = false
```

Missing project notes, missing decision evidence, and missing connect
inventory stay UNKNOWN. A readable vault never becomes owner authority.
