# AS-CODER-ALPHA-AUTHZ-READ-001

Vault-scoped operator-profile **REPORT READ** wrap over the existing
`GET /v1/authz` projection (AS-2.1-AUTHZ-001).

```
atlas authz report --vault <dir> [--json]
atlas authz show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/authz/report` (honesty-wrapped wrap; does not replace `GET /v1/authz`)
- MCP `atlas.authz.read` (zero-arg, vault-scoped, vault-read)

Existing `GET /v1/authz` remains the AS-2.1-AUTHZ-001 operator profile
projection (`authority=false`, `write_enabled=false`). This package
reads that projection. It does **not** grant write, does **not** mint
sessions, does **not** elevate, and does **not** invent OWNER / MERGE /
SECURITY authority.

Honesty (mandatory):

- `AUTHZ != AUTHORITY`
- `PROFILE != GRANT`
- `CAPABILITY_LIST != OWNER_GATE`
- `WRITE_ENABLED=false`
- `MCP != AUTHORITY`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed, never a grant. Listing
capabilities is not an owner gate. Web page skipped (existing
`/v1/authz` already owns the live operator profile).

Does not touch `atlas3/` or D-149.

Examples:

```
atlas authz report --vault /path/to/vault
atlas authz report --vault /path/to/vault --json
atlas authz show --vault /path/to/vault --json
```
