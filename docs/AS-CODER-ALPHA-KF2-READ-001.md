# AS-CODER-ALPHA-KF2-READ-001

Vault-scoped Knowledge Fabric **REPORT READ** lens over existing
AS-KF2-NS-001 / AS-KF2-ENTITY-001 / AS-KF2-REL-001 projections persisted
under `generated/kf2/{namespaces,entities,relationships}/`.

```
atlas kf2 report --vault <dir> [--json]
atlas kf2 show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/kf2`
- MCP `atlas.kf2.read` (zero-arg, vault-scoped)

`atlas kf2 namespace`, `atlas kf2 entity`, and `atlas kf2 rel` remain the
existing write surfaces. This package does **not** register namespaces,
entities, or relationships, and does **not** write KF2 inventory.

Honesty (mandatory):

- `KF2 != AUTHORITY`
- `NAME != IDENTITY`
- `MISSING != REGISTERED`
- `EMPTY != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed `UNKNOWN`, never healthy or
registered. Malformed JSON and path escape fail closed. Web page skipped
(would bloat; sibling wraps already own nav surface).

Does not touch `atlas3/` or D-149.

Examples:

```
atlas kf2 report --vault /path/to/vault
atlas kf2 report --vault /path/to/vault --json
atlas kf2 show --vault /path/to/vault --json
```
