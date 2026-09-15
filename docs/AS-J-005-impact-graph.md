# AS-J-005 — Derived Impact Graph

**Package:** AS-J-005 (backlog **J-005**)  
**Stream:** Epic J — Incremental operation (FR-013 / AT-017)  
**Status:** Implementation complete — IV-ready (governor certification required)  
**Depends on:** AS-GRAPH-003 retained relationships (consume-only)  
**Truth boundary:** `IMPACT GRAPH ≠ AUTOMATIC AUTHORITY`

## Purpose

Build a deterministic **derived** impact adjacency projection from existing
GRAPH-003 relationship stores so incremental refresh can answer:

> If entity *X* changes, which other entities are directly impacted?

Never invents authority winners, trust scores, or claim dispositions.

## Persistence

Library entrypoints: `compile_impact_graph` / `write_impact_graph` /
`impacted_entity_ids`.

| Path | Role |
|---|---|
| `generated/indexes/impact-graph.json` | Derived vault-wide impact projection |

**Forbidden:** Control Plane `relationships/`, claims, GRAPH-002/003/004
certified machine-store prefixes (consume-only), GRAPH-005 projections,
`apps/web`, INT retention writers, `recover_promote_orphans`.

## Impact polarity (from GRAPH-003 edge source→target)

| Relationship type | Impact direction |
|---|---|
| `depends-on`, `derived-from` | target → source |
| `documents`, `validates`, `extension`, `supersedes` | source → target |
| `part-of`, `conflicts-with` | bidirectional |

## Invariants

- `IMPACT GRAPH ≠ AUTOMATIC AUTHORITY`
- `authority.level` is always `derived`
- Deterministic ordering; `generated.by` only (no wall-clock)
- Empty relationship store ⇒ empty entities/edges (no speculation)
- Schema: `impact-graph`

## Out of scope

CLI dual-own of GRAPH-005 / QUERY / EXPLAIN, authority invent, REL-001,
PILOT invent, promote recovery, INT-009 retention writers, `apps/web`.
