# Estate intelligence slice — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

Package: **AS-2.2-INTEL-SLICE-PREP-001**

## Intent

Provide a **deterministic intelligence slice** that composes cite-only inputs from
KF fabric, hybrid retrieval / context packs, temporal validity, and conflict
projections into one derived envelope for Ask / MCP / Estate-Ops / UI lenses —
without mutating those substrates and without elevating derived ranks to
authority.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Lenses (Ask / MCP / Estate-Ops / UI) — consume-only        │
│  UI ≠ canonical · Graph ≠ authority · LLM ≠ authority       │
├─────────────────────────────────────────────────────────────┤
│  2.2 Intelligence slice (future AS-2.2-INTEL-SLICE-001)     │
│    compose(scope, inputs) → IntelligenceSliceEnvelope       │
│    explain(slice_id) → citation + unknown + conflict view   │
├─────────────────────────────────────────────────────────────┤
│  Upstream prep / post-unlock lanes (consume only)           │
│    AS-2.2-KF2-FABRIC-* inventory / projection citations     │
│    AS-2.2-RET-CTX-001 / RET-HYBRID context-pack citations   │
│    AS-2.2-TEMPORAL-* validity / unknown citations           │
│    AS-2.2-CONFLICT-UX-* open conflict / review citations    │
├─────────────────────────────────────────────────────────────┤
│  Substrate (certified / on-main — conceptual only)          │
│    AS-CORE-003 claims / authority / conflicts               │
│    AS-RET-001 lexical retrieval                             │
│    AS-KF2-* namespaces / entities / relationships           │
│    AS-CORE-005 / bitemporal validity windows                │
└─────────────────────────────────────────────────────────────┘
```

## Composition model

An intelligence slice is a **derived, deterministic** envelope:

| Field | Rule |
|---|---|
| `scope` | Explicit project / estate slice id (no implicit whole-estate merge) |
| `inputs.kf_fabric[]` | Cite KF inventory / projection ids only |
| `inputs.retrieval[]` / `inputs.context_packs[]` | Cite plan / pack ids only |
| `inputs.temporal[]` | Cite validity receipts; unresolved → `unknown`, never invent |
| `inputs.conflicts[]` | Cite open conflict / review ids; retain unresolved |
| `unknown[]` | Fail-closed leftovers (missing citation, unresolved temporal, quarantine) |
| `authority.level` | Always `derived` |
| `canonical_write` | Always `false` |
| `atlas_2_1_release_certified` | `false` on all prep fixtures |
| `pilot_roots` | `0` |
| `evidence_class` | `fixture-only` in this PREP |
| `generated` | `{ "by": "..." }` only — never `at` (NFR-001) |

## Truth boundaries

```text
INTEL SLICE ≠ AUTHORITY
INTEL SLICE ≠ LAYER B WRITE
INTEL SLICE ≠ SILENT CONFLICT RESOLVE
INTEL SLICE ≠ PILOT / RELEASE / UNLOCK CREDIT
LLM ≠ AUTHORITY · UI ≠ CANONICAL · GRAPH ≠ AUTHORITY
```

## Non-goals

- Runtime modules under `src/project_atlas/` or web/API/MCP servers
- Dual-owning KF2 / RET / TEMPORAL / CONFLICT-UX emit trees
- Elevating fused ranks to Layer B claims
- Silent conflict winners or auto-resolve policies
- Subjective trust / confidence scores
- Authentic estate PILOT evidence from fixtures
- Flipping `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: slice prep never calls `_promote` / never mutates Layer B
- Evidence refs remain project-scoped even when a global / KF id exists
