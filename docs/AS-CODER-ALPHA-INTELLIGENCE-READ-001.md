# AS-CODER-ALPHA-INTELLIGENCE-READ-001

Vault-scoped derived-intelligence **REPORT READ** index over existing
`/v1/intelligence/{evidence,conflicts,explain,query}` views.

```
atlas intelligence report --vault <dir> [--json]
atlas intelligence show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/intelligence` (zero-arg index/status; does not collide with the
  project-scoped sub-routes)
- MCP `atlas.intelligence.read` (zero-arg, vault-scoped)

Existing `GET /v1/intelligence/evidence|conflicts|explain|query` remain the
project-scoped derived readers. This package does **not** compute those
answers, does **not** write Layer B, and does **not** treat graph or
derived intelligence as Truth Core.

Honesty (mandatory):

- `INTELLIGENCE != AUTHORITY`
- `GRAPH != AUTHORITY`
- `DERIVED != TRUTH CORE`
- `EMPTY != HEALTHY`
- `UNKNOWN != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed `UNKNOWN`, never healthy. Empty
`projects/` is `EMPTY`, never healthy. Web page skipped (existing
`#/intelligence` already owns the project-scoped views).

Does not touch `atlas3/` or D-149.

Examples:

```
atlas intelligence report --vault /path/to/vault
atlas intelligence report --vault /path/to/vault --json
atlas intelligence show --vault /path/to/vault --json
```
