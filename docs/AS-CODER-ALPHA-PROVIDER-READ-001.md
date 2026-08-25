# AS-CODER-ALPHA-PROVIDER-READ-001

Vault-scoped provider **REPORT READ** lens over persisted
AS-2.0-PROV-001 artifacts:

- `generated/ops/provider-adapter-registry.json`
- `generated/ops/provider-quarantine/*.json`

```
atlas provider report --vault <dir> [--json]
atlas provider show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/provider`
- MCP `atlas.provider.read` (zero-arg, vault-scoped, vault-read)

`atlas provider registry` and `atlas provider quarantine` remain the
existing writers. This package does **not** write a registry, quarantine
new output, enable live SDKs, or dispatch `atlas.provider.generate`.

Honesty (mandatory):

- `PROVIDER != AUTHORITY`
- `REGISTRY != LIVE SDK`
- `QUARANTINE != APPROVED`
- `MISSING != ENABLED`
- `EMPTY != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed `UNKNOWN`, never ENABLED or
healthy. Malformed JSON, schema-invalid reports, claimed live SDK /
`adapters_enabled`, claimed approved quarantine, and path escape fail
closed. Web page skipped (would bloat; sibling wraps already own nav
surface).

Does not touch `atlas3/` or D-149. Does not implement `atlas.obs.read`.
Does not retouch kci / lifecycle / xproj / schema-compat / #511.
