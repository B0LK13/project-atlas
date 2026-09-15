# Conflict projection cockpit — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Provide a **read-only conflict projection + review cockpit** that surfaces
duplicate-source facets, pending CONFLICT reviews, and authority dispositions
for operators / Ask / MCP consumers — without mutating the Core conflict spine
or inventing a second durable review-queue root.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Cockpit / Ask / MCP lenses — consume-only                  │
│  UI ≠ canonical · Graph ≠ conflict invent · LLM ≠ authority │
├─────────────────────────────────────────────────────────────┤
│  2.2 Conflict UX service (future AS-2.2-CONFLICT-UX-001)    │
│    panel(scope) → ConflictCockpitPanel                      │
│    queue(scope) → ConflictReviewQueueView                   │
│    facet(conflict_id) → ConflictProjectionFacet             │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on main — consume only / conceptual)    │
│    AS-CORE-003 claims / conflicts / review emit             │
│    AS-CORE2-008 conflict_projections + review honesty       │
│    review/conflicts/ + review/pending/ (single roots)       │
│    generated/indexes/conflicts.json + reviews.json          │
├─────────────────────────────────────────────────────────────┤
│  Adjacent (do not dual-own)                                 │
│    AS-GRAPH-* relationships (≠ conflict mint)               │
│    AS-XPROJ-004 cross-project conflict indexes              │
│    AS-2.2-RESEARCH-001 Ask Atlas CONFLICTS field            │
└─────────────────────────────────────────────────────────────┘
```

## Substrate mapping

| Bucket | Source package | Emit path (frozen on main) | Prep rule |
|---|---|---|---|
| Conflict records | AS-CORE-003 | write-plan → vault conflicts | Consume-only |
| Duplicate-source facets | AS-CORE2-008 | projection helpers | Label-only; no new ConflictType |
| Review entries | AS-CORE-003 / CORE2-008 | `review/conflicts/`, `review/pending/` | One queue root |
| Lexical companions | AS-CORE2-008 / indexes | `generated/indexes/conflicts.json`, `reviews.json` | Companion ≠ queue |
| Authority dispositions | AS-CORE-003 | authoritative state records | Consume; never invent trust |

## Cockpit panel (conceptual)

A panel result is a **derived, deterministic** envelope:

- `scope` — explicit project / subject slice (no implicit estate merge)
- `conflicts[]` — citations by `conflict_id` only
- `facets[]` — duplicate-source / disposition labels (`kind` controlled)
- `reviews[]` — pending CONFLICT category entries by `review_id`
- `authority.level = derived`
- `canonical_write = false`
- `silent_resolve = false`
- `second_queue_root = false`
- `atlas_2_1_release_certified = false` on all prep fixtures

## Non-goals

- Mutating `project_atlas.conflict_projections` or dual-owning `review/`
- Inventing Core conflicts from Graph edges or XPROJ indexes
- Silent authority winners / auto-resolve policies
- Subjective trust / confidence scores
- Authentic estate PILOT evidence from fixtures

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: cockpit prep never calls `_promote` / never mutates Layer B
- Evidence refs remain project-scoped
