# Evidence — AS-CODER-ALPHA-VALIDATE-MCP-001

PACKAGE: `AS-CODER-ALPHA-VALIDATE-MCP-001`
BRANCH: `cursor/atlas-autonomous-night-cycle-f2d9`
BASE_MAIN: `f0e0c979e8ead0fdad4cc51682c560299db0a074`
BASE_TREE: `ba83d96a3542f270ae99c03b59da97b0ce567ac4`

## Honesty

- `VALIDATE != AUTHORITY`
- `OK != HEALTHY`
- `OK != PILOT`
- `MCP != AUTHORITY`
- `UI != CANONICAL`
- `MERGE_AUTHORIZATION = NOT_GRANTED`
- `AUTHENTIC_PILOT = NO`
- `D149_TOUCHED = NO`

## Surfaces

- `GET /v1/validate`
- MCP `atlas.validate.read` (zero-arg)
- Web `#/validate`

## Independent verification

IV_RESULT=PASS at `7c5c64a630731d62701703d210e899789b2e97ad` /
TREE `f9922bc4d956053fa3cd0399d6b732ae937417a4` (worktree
`/tmp/iv-validate-mcp-f2d9`; 24 passed; P0=0 P1=0). Implementer ≠ verifier.
Do not transfer this IV to later HEADs without re-run.

## D-149

Draft `#483` remains the D-149 candidate. This package does not duplicate or
merge that work.
