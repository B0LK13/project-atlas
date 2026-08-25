# AS-CODER-ALPHA-SCHEMA-COMPAT-READ-001

Vault-scoped schema-compat **REPORT READ** lens over the existing AS-INT-012
`generated/ops/schema-compat-report.json` reader.

```
atlas schema report --vault <dir> [--json]
atlas schema show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/schema-compat`
- MCP `atlas.schema.compat.read` (zero-arg, vault-scoped)

`atlas schema compat` / `atlas schema migrate` remain the write/scan and
dry-run surfaces. This package does **not** scan, write, or apply a
migration.

Honesty (mandatory):

- `REPORT != AUTHORITY`
- `SCHEMA-COMPAT != MIGRATION APPLY`
- `LENS != TRUTH CORE`
- Missing report is `UNKNOWN` / `REPORT_ABSENT`, never compatible
- Web page skipped (would bloat; sibling wraps already own nav surface)

Does not touch `atlas3/` or D-149.
