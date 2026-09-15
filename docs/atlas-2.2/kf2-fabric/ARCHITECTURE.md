# Knowledge Fabric estate — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Provide an **estate-scale KF inventory / projection lens** that composes the
certified AS-KF2-* primitives into a single deterministic inventory for future
estate-ops / Ask / MCP / KCI consumers — without mutating those primitives'
write surfaces and without cross-promoting derived rows into Layer B.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Lenses (UI / Ask / MCP / Estate-Ops / KCI) — consume-only  │
│  UI ≠ canonical · Graph ≠ authority · LLM ≠ authority       │
├─────────────────────────────────────────────────────────────┤
│  2.2 KF fabric service (future AS-2.2-KF2-FABRIC-001)       │
│    inventory(scope) → Kf2EstateFabricInventory              │
│    project(scope, buckets) → Kf2EstateProjection            │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on main — consume only / conceptual)    │
│    AS-KF2-NS-001 namespaces                                 │
│    AS-KF2-ENTITY-001 entities                               │
│    AS-KF2-REL-001 relationships                             │
│    AS-KF2-002 inventory export (counts; cross_promote=false)│
├─────────────────────────────────────────────────────────────┤
│  Adjacent (do not dual-own)                                 │
│    AS-XPROJ-* cross-project registry / edges / indexes      │
│    AS-GRAPH-003 intra-project relationships                 │
│    AS-CORE-003 claims / authority                           │
│    AS-2.0-FED-* multi-vault federation                      │
└─────────────────────────────────────────────────────────────┘
```

## Substrate mapping

| Bucket | Source package | Emit path (frozen on main) | Prep rule |
|---|---|---|---|
| Namespaces | AS-KF2-NS-001 | `generated/kf2/namespaces/` | Consume-only |
| Entities | AS-KF2-ENTITY-001 | `generated/kf2/entities/` | Consume-only; optional XPROJ cite ≠ authority |
| Relationships | AS-KF2-REL-001 | `generated/kf2/relationships/` | Consume-only; Graph≠authority |
| Inventory export | AS-KF2-002 | `generated/ops/kf2/*.json` | Counts only; `cross_promote=false` |

## Fabric inventory (conceptual)

An estate inventory result is a **derived, deterministic** envelope:

- `scope` — explicit project set / estate slice (no implicit whole-estate merge)
- `namespaces[]` / `entities[]` / `relationships[]` — citations by id only
- `inventory_refs[]` — AS-KF2-002 export citations (counts; not Layer B)
- `quarantine[]` — fail-closed leftovers (malformed id, missing endpoint, cross-promote attempt)
- `cross_promote = false`
- `authority.level = derived`
- `truth_boundary` constant documenting non-authority
- `atlas_2_1_release_certified = false` on all prep fixtures

## Estate projection (conceptual)

A projection result is a **read-only slice** over selected KF buckets:

- cites substrate ids only
- never writes under `generated/kf2/` or `generated/ops/kf2/`
- never elevates `authority.level` beyond `derived`
- never sets `cross_promote: true`

## Non-goals

- Replacing AS-KF2-* runtimes or dual-owning their emit trees
- Multi-vault federation productization (deferred; FED remains separate)
- Elevating KF fabric rows to Layer B claims or domain authority
- Authentic estate PILOT evidence from fixtures
- Forking shipped `kf2-*.schema.json` package ids in this PREP

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: fabric prep never calls `_promote` / never mutates Layer B
- Evidence refs remain project-scoped even when a global / KF id exists
