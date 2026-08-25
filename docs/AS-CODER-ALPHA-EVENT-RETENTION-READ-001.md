# AS-CODER-ALPHA-EVENT-RETENTION-READ-001

Vault-scoped event-retention **REPORT READ** lens over the existing AS-INT-009
`generated/ops/retention-report.json` reader.

```
atlas retention report --vault <dir> [--json]
atlas retention show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/event-retention`
- MCP `atlas.event.retention.read` (zero-arg, vault-scoped)

`atlas retention apply` remains the write/apply surface. This package does
**not** apply retention, delete packages/receipts, or write Layer B.

Honesty (mandatory):

- `REPORT != AUTHORITY`
- `RETENTION REPORT != APPLY`
- `LENS != TRUTH CORE`
- Missing report is `UNKNOWN` / `REPORT_ABSENT`, never applied
- Web page skipped (would bloat; sibling wraps already own nav surface)

Does not touch `atlas3/` or D-149.
