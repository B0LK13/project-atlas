# AS-CODER-ALPHA-LIFECYCLE-READ-001

Vault-scoped lifecycle **REPORT READ** lens over the persisted
AS-CORE2-010 fixture lifecycle-certify report
(`generated/ops/lifecycle-cert-report.json`).

```
atlas lifecycle report --vault <dir> [--json]
atlas lifecycle show --vault <dir> [--json]    # alias; still read-only
```

Also:

- `GET /v1/lifecycle`
- MCP `atlas.lifecycle.read` (zero-arg, vault-scoped)

`atlas lifecycle certify` remains the fixture-safe writer. This package
does **not** run the lifecycle matrix, write a certify report, or claim
estate PILOT PASS.

Honesty (mandatory):

- `LIFECYCLE != AUTHORITY`
- `CERTIFY_REPORT != PILOT PASS`
- `MISSING != CERTIFIED`
- `EMPTY != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED = false`
- `D149_TOUCHED = NO`
- `src/project_atlas/atlas3/** UNTOUCHED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Foreign or missing vault is fail-closed `UNKNOWN`, never CERTIFIED or
healthy. Malformed JSON, schema-invalid reports, claimed
`estate_pilot_passed`, and path escape fail closed. Web page skipped
(would bloat; sibling wraps already own nav surface).

Does not touch `atlas3/` or D-149.
