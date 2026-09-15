# AS-GRAPH-005 — Human-Readable Derived Graph Projections

**Package:** AS-GRAPH-005  
**Stream:** Atlas Graph Layer  
**Status:** Implementation complete — IV-ready (governor certification required)  
**Depends on:** AS-GRAPH-003 retained relationships + AS-GRAPH-004 health snapshots (consume-only)  
**Truth boundary:** `GRAPH PROJECTION ≠ AUTOMATIC AUTHORITY`

## Purpose

Emit human-facing Markdown projections from machine graph state only, through a
Core-safe promote boundary, without overriding Layer A evidence, claim stores,
or Control Plane `relationships/`:

- `relationships.md` — source-linked derived relationships for a project
- `graph-health.md` — categorical health / quarantine summary (metadata counters)

**Critical rule:** projections are derived intelligence views ≠ domain authority
≠ Layer A evidence. Link-quality / health counters are not trust scores.

## Persistence

Library entrypoints: `materialize_projections` /
`materialize_projections_from_vault` / `write_projection_outputs`.

Optional vault emits are restricted to:

| Path | Role |
|---|---|
| `generated/graph/projections/<project_id>/relationships.md` | Derived relationship projection |
| `generated/graph/projections/<project_id>/graph-health.md` | Derived health projection |

**Forbidden:** Control Plane `relationships/`, claims, temporal/authoritative
state, GRAPH-002/003/004 certified machine-store prefixes (consume-only),
knowledge-query caches.

## Content rules

- Every shown relationship remains labeled `derived / source-linked`
- Explicit “derived intelligence — not Layer A evidence” banner
- Quarantine / health summaries are metadata-only
- Secret-shaped tokens redacted from projection text
- Deterministic ordering (type → source → target → id)
- Absence of graph state ⇒ explicit absent status; no speculative content
- Protected HUMAN regions preserved byte-for-byte; malformed markers fail closed (AT-011)
- Failed promote leaves prior projection bytes intact
- No wall-clock timestamps (`generated_by` only)

## Invariants

- `GRAPH PROJECTION ≠ AUTOMATIC AUTHORITY`
- `GRAPH HEALTH ≠ PROJECT AUTHORITY` (health view inherits GRAPH-004 boundary)
- AS-GRAPH-INV-TRUTH-001 held — projections never elevate graph to claim truth
- AS-GRAPH-002/003/004 certified semantics unchanged (consume-only)
- No CP `relationships/` writes

## Out of scope

Deferred laundry list (`dependencies.md`, Mermaid UX, estate dashboards),
CLI QUERY/EXPLAIN surfaces, dual-own of XPROJ-002 / EXPLAIN Band B /
QUERY-MULTI, `knowledge_compiler` mutation, reopening closed packages.
