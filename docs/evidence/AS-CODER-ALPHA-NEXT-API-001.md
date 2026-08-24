# Evidence — AS-CODER-ALPHA-NEXT-API / WEB / MCP

DIRECTIVE: autonomous night cycle 2026-08-24T23:10Z
PACKAGES: `AS-CODER-ALPHA-NEXT-API-001`, `AS-CODER-ALPHA-NEXT-WEB-001`, `AS-CODER-ALPHA-NEXT-MCP-001`
BRANCH: `cursor/atlas-autonomous-night-cycle-02ff`
EXACT_MAIN: `f0e0c979e8ead0fdad4cc51682c560299db0a074`
MAIN_TREE: `ba83d96a3542f270ae99c03b59da97b0ce567ac4`

```
NEXT LENS != AUTHORITY
NEXT ACTION != COMMAND
UI != CANONICAL TRUTH
MCP != AUTHORITY
D149_IMPLEMENTED_ON_THIS_BRANCH = NO
AUTHENTIC_PILOT = NO
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Live-state note

D-149 owner-gate non-escalation remains on draft `#477` (`c54f9ea`). Independent
IV this cycle: live main still clears non-estate `CREDENTIAL` and rewrites
`SUPERSEDED MERGE` → `CREDENTIAL`. `#477` remediates. This package does not
duplicate `#471`–`#480`.

## Change

- `GET /v1/next?project=` projects `build_next_lens` (read-only)
- Web `#/next` consumes that API; no fixture default
- Zero-arg vault-scoped `atlas.next.read`

## Honesty

Does not claim authentic O2. Does not merge. Does not grant owner authority.
`#406` remains historical; this is a current-main reconstruction.
