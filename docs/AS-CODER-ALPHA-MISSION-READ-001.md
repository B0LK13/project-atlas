# AS-CODER-ALPHA-MISSION-READ-001

Vault-scoped mission **REPORT READ** wrap over the existing
`GET /v1/mission` derived view (AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001).

```
atlas mission report --vault <dir> [--json]
atlas mission show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/mission/report` (honesty-wrapped wrap; does not replace `GET /v1/mission`)
- MCP `atlas.mission.read` (zero-arg, vault-scoped, vault-read)

Existing `GET /v1/mission` remains the AS-2.1 live mission composition
(`authentic_pilot=false`, `pilot_estate_rows=[]`, `ui_canonical=false`).
This package reads that derived view. It does **not** write mission
state, does **not** invent PILOT rows, and does **not** treat the
mission view as Truth Core or authority.

Honesty (mandatory):

- `MISSION != AUTHORITY`
- `VIEW != TRUTH CORE`
- `EMPTY != HEALTHY`
- `UNKNOWN != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed, never healthy. An empty
mission view is `EMPTY`, never healthy. An unread or unknown rollup
with projects present is `UNKNOWN`, never healthy. Web page skipped
(existing `/v1/mission` already owns the live derived view).

Does not touch `atlas3/` or D-149.

Examples:

```
atlas mission report --vault /path/to/vault
atlas mission report --vault /path/to/vault --json
atlas mission show --vault /path/to/vault --json
```
