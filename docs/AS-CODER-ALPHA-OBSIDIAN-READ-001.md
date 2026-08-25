# AS-CODER-ALPHA-OBSIDIAN-READ-001 — vault-scoped living-note inventory

Package ID: `AS-CODER-ALPHA-OBSIDIAN-READ-001`.

Read-only inventory of existing Coder Alpha living notes under
`generated/obsidian/projects/<id>/project-living.md`. Does not call
`atlas obsidian project`.

## Surfaces

- MCP: zero-arg `atlas.obsidian.read`
- LIVE_API: `GET /v1/obsidian` (optional `?project=`)
- Web: `#/obsidian` (optional `?project=`)
- CLI: `atlas obsidian list` (read-only; `project` still materializes)

## Honesty

- `PROJECTION != AUTHORITY`
- `PROJECTION != PLUGIN`
- `MCP != WRITE`
- `UI != CANONICAL`
- Empty inventory is UNKNOWN, not a healthy zero
- Human-region text is not echoed (presence only)
- No request args on MCP; project filter is LIVE_API/Web/CLI only
- `AUTHENTIC_PILOT = NO`

## Non-goals

- D-149 owner-gate remediation (remains draft `#483`)
- Obsidian plugin shipping
- Authentic O2
- Merge authorization
