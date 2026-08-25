# AS-CODER-ALPHA-WORKSPACE-READ-001

Vault-scoped workspace **REPORT READ** wrap over the existing
`GET /v1/workspace` derived view (AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001).

```
atlas workspace report --vault <dir> [--json]
atlas workspace show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/workspace/report` (honesty-wrapped wrap; does not replace `GET /v1/workspace`)
- MCP `atlas.workspace.read` (zero-arg, vault-scoped, vault-read)

Existing `GET /v1/workspace` remains the AS-2.1 live workspace composition
(`authentic_pilot=false`, `pilot_estate_rows=[]`, `ui_canonical=false`).
This package reads that derived view. It does **not** write workspace
state, does **not** invent PILOT rows, and does **not** treat the
workspace view as Truth Core or authority.

Honesty (mandatory):

- `WORKSPACE != AUTHORITY`
- `VIEW != TRUTH CORE`
- `EMPTY != HEALTHY`
- `UNKNOWN != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed, never healthy. An empty
workspace view is `EMPTY`, never healthy. An unread or unknown rollup
with projects present is `UNKNOWN`, never healthy. Web page skipped
(existing `/v1/workspace` already owns the live derived view).

Does not touch `atlas3/` or D-149.

Examples:

```
atlas workspace report --vault /path/to/vault
atlas workspace report --vault /path/to/vault --json
atlas workspace show --vault /path/to/vault --json
```
