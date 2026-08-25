# AS-CODER-ALPHA-XPROJ-READ-001

Vault-scoped cross-project **REPORT READ** lens over existing AS-XPROJ-001
registry, AS-XPROJ-002 edges, and AS-XPROJ-003 duplicate-candidate
projections.

```
atlas xproj report --vault <dir> [--json]
atlas xproj show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/xproj`
- MCP `atlas.xproj.read` (zero-arg, vault-scoped)

`atlas register-global-entity`, `atlas register-global-edge`, and
`atlas detect-project-duplicates` remain the write/register surfaces.
This package does **not** write edges, register or join identities, or
merge identities.

Honesty (mandatory):

- `XPROJ != AUTHORITY`
- `GRAPH != AUTHORITY`
- `LENS != TRUTH CORE`
- `MISSING != NO_EDGES` / `MISSING != HEALTHY`
- `EMPTY != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed `UNKNOWN`, never healthy.
Web page skipped (would bloat; sibling wraps already own nav surface).

Does not touch `atlas3/` or D-149.
