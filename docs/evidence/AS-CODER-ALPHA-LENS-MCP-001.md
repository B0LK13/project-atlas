# Evidence — AS-CODER-ALPHA-LENS-MCP-001

DIRECTIVE: Autonomous night cycle 2026-08-25-0250
PACKAGE: `AS-CODER-ALPHA-LENS-MCP-001`
BRANCH: `cursor/atlas-autonomous-night-cycle-b4cd`
EXACT_MAIN: `f0e0c979e8ead0fdad4cc51682c560299db0a074`

```
MCP LENS != AUTHORITY
UNKNOWN VALID
NO WRITE
NO INVENTORY ROTATE
OWNER_CAPABILITY_GRANTED = false
D149_TOUCHED = NO
AUTHENTIC_PILOT = NO
INDEPENDENT_IV = PENDING
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Change

Zero-arg vault-scoped MCP tools:

- `atlas.overview.read`
- `atlas.decisions.read`
- `atlas.unknown.read`
- `atlas.changed.read`

Changed reads existing connect inventories only. It does not rotate
`connect-inventory.json` and does not write `generated/answers`.

## Surfaces not touched

`authentic_estate.py`, mission reconciler, CLI flags, web routes, D-149 tests.
