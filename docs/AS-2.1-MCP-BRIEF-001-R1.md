# AS-2.1-MCP-BRIEF-001-R1

Successor transplant of certified `#365` (`AS-2.1-MCP-BRIEF-001`) onto
current `main`. Ledger files (`WORKLOG.md`, `docs/backlog.md`) are not
copied. This document is the package-specific successor note.

## Purpose

Expose a zero-argument, vault-scoped, read-only MCP tool
`atlas.brief.read` that returns Coder Alpha project briefs already
present in the vault. UNKNOWN stays UNKNOWN. MCP output is not
authority.

## Invariants (preserved from #365)

- Authz required: `mcp.read`
- Zero write authority (`write_tools == []`; no vault mutation)
- Malformed / unexpected / forbidden request keys fail closed
- Cross-project isolation: one project's brief does not leak another
- No implicit authority elevation (`mcp_is_authority=false`,
  `lens_is_authority=false`, `portfolio_implicit_all=false`)
- Empty vault does not invent projects or briefs
- Missing brief file is UNKNOWN, not fabricated

## Non-claims

- Not a write tool and not an estate scan
- MODEL OUTPUT != AUTHORITY
- MCP LIVE != WRITE / != AUTHORITY
- OWNER_HELD = YES; MERGE_AUTHORIZATION = NOT_GRANTED
- Does not mutate certified `#365` / `#366` heads
