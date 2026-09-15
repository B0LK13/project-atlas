# Cross-project fabric — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Provide an **estate-scale fabric lens** that composes the certified AS-XPROJ-*
primitives into a single deterministic inventory for future estate-ops /
Ask / MCP consumers — without mutating those primitives' write surfaces.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Lenses (UI / Ask / MCP / Estate-Ops) — consume-only        │
│  UI ≠ canonical · Graph ≠ authority · LLM ≠ authority       │
├─────────────────────────────────────────────────────────────┤
│  2.2 Fabric inventory service (future AS-2.2-XPROJ-001)     │
│    inventory(scope) → XprojFabricInventory                  │
│    lens(scope, buckets) → XprojEstateLens                   │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on main — consume only / conceptual)    │
│    AS-XPROJ-001 global entities + joins                     │
│    AS-XPROJ-002 cross-project edges                         │
│    AS-XPROJ-003 duplicate / successor candidates            │
│    AS-XPROJ-004 derived indexes + conflict reports          │
├─────────────────────────────────────────────────────────────┤
│  Adjacent (do not dual-own)                                 │
│    AS-GRAPH-003 intra-project relationships                 │
│    AS-RET-001 lexical indexes                               │
│    AS-CORE-003 claims / authority                           │
└─────────────────────────────────────────────────────────────┘
```

## Substrate mapping

| Bucket | Source package | Emit path (frozen on main) | Prep rule |
|---|---|---|---|
| Entities | AS-XPROJ-001 | `state/global-entities/*.json` | Consume-only |
| Joins | AS-XPROJ-001 | `state/global-entities/joins/*.json` | Explicit only |
| Edges | AS-XPROJ-002 | `state/global-entities/edges/*.json` | ≥2 projects |
| Duplicate candidates | AS-XPROJ-003 | `generated/xproj/duplicate-candidates/` | No autocollapse |
| Indexes | AS-XPROJ-004 | `generated/xproj/indexes/**` | ≠ RET-001 |
| Conflicts | AS-XPROJ-004 | `generated/xproj/conflicts/**` | No auto-resolve |

## Fabric inventory (conceptual)

An inventory result is a **derived, deterministic** envelope:

- `scope` — explicit project set / estate slice (no implicit whole-estate merge)
- `entities[]` / `joins[]` / `edges[]` — citations by id only
- `duplicate_candidates[]` — review candidates; `autocollapse: false`
- `index_buckets[]` — derived index refs (not lexical RET)
- `conflicts[]` — conflict report refs (not Core claim synthesis)
- `quarantine[]` — fail-closed leftovers (fuzzy, missing endpoint, not-cross-project)
- `authority.level = derived`
- `truth_boundary` constant documenting non-authority
- `atlas_2_1_release_certified = false` on all prep fixtures

## Non-goals

- Replacing AS-XPROJ-001–004 runtimes or dual-owning their emit trees
- Multi-vault federation productization (deferred; FED remains separate)
- Display-name / fuzzy / embedding / LLM identity merges
- Elevating fabric edges to Layer B claims or domain authority
- Authentic estate PILOT evidence from fixtures

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: fabric prep never calls `_promote` / never mutates Layer B
- Evidence refs remain project-scoped even when a global ID exists
