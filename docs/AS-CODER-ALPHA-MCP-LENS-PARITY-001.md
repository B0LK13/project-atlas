# AS-CODER-ALPHA-MCP-LENS-PARITY-001

Allow-listed read-only MCP tools for Coder Alpha lenses already on main:

- `atlas.source-health.read` → `explain_source_health`
- `atlas.attention.read` → `classify_attention`
- `atlas.next.read` → `derive_next_lenses` (never `materialize_next_lenses`)

```
{"tool": "atlas.source-health.read", "project": "<id>"}
{"tool": "atlas.attention.read", "project": "<id>"}
{"tool": "atlas.next.read", "project": "<id>"}
```

## Invariants

- Allow-list only. Unknown tools fail closed.
- Project scope required. No implicit portfolio-all.
- MCP LENS != AUTHORITY. UNKNOWN is valid.
- `WRITE_CONTROLS=0`. No vault writes. No Layer B mutation.
- `SECRET_ECHO=NO`.
- `CROSS_PROJECT_LEAK_COUNT=0`.
- Path traversal in tool or project identifiers is rejected.
- Zero-arg tools (`atlas.brief.read` and peers) still reject `project`.
- CLI JSON shape is preserved where practical; MCP honesty is additive.

## Non-claims

- Does not retarget `#370` AS-2.1-MCP-BRIEF-001-R1.
- Does not rewrite `#414` six-lens production adapters.
- Does not replace LIVE_API `/v1/source-health` or `atlas` CLI commands.
- MCP output is derived, not Truth Core.
