# AS-CODER-ALPHA-KCI-READ-001

Vault-scoped Knowledge CI **REPORT READ** lens over existing AS-2.0-KCI-001
compile requests/receipts and AS-2.0-KCI-HARNESS-001 harness records.

```
atlas kci report --vault <dir> [--json]
atlas kci show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/kci`
- MCP `atlas.kci.read` (zero-arg, vault-scoped)

`atlas kci request` and `atlas kci receipt` remain the consume-only write
surfaces. This package does **not** issue compile requests, write receipts,
or run the Knowledge CI harness.

Honesty (mandatory):

- `KCI != AUTHORITY`
- `RECEIPT != CERTIFICATION`
- `EMPTY != HEALTHY`
- `MISSING != PASS`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed `UNKNOWN`, never healthy or PASS.
Malformed JSON and path escape fail closed. Web page skipped (would bloat;
sibling wraps already own nav surface).

Does not touch `atlas3/` or D-149.
