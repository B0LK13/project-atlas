# AS-2.0-CTX-001 — Context assembly packs

| Field | Value |
|---|---|
| Package | **AS-2.0-CTX-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (thin contract) |
| Class | **READY** (depends on AS-2.0-COMPAT-001; soft after KCI) |
| Compat pin | `require_compatibility_anchor` / `atlas-1.0.0-compat` |

## Purpose

Fixture-safe context packs that assemble bounded retrieval / receipt /
index pointers for agents and UX without inventing estate facts.

## Surfaces

| Kind | Path |
|---|---|
| Schema | `context-pack` |
| Module | `project_atlas.context_pack` |
| CLI | `atlas context-pack build` |

## Truth boundary

`CONTEXT PACK ≠ ESTATE FACTS / ≠ PILOT`

- `fixture_safe` is always `true`
- `estate_facts_invented` is always `false`
- `provenance_pointers` is mandatory (`minItems: 1`)
- Attempts to invent estate facts fail closed

## Non-claims

- Not automatic PILOT estate injection
- Not inventing missing evidence as healthy / present
- Not Atlas 2.0 RELEASE CERTIFIED
- Not authentic ESTATE PILOT PASS
- Not OpenAI/MCP production wiring
