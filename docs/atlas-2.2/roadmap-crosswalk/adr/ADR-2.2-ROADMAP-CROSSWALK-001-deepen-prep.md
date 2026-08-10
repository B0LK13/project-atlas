# ADR-2.2-ROADMAP-CROSSWALK-001 — Roadmap crosswalk deepen prep

| Field | Value |
|---|---|
| Package | AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001 |
| Status | Accepted for **PREP only** |
| Tip audited | `7f9692aeaa163d185e916713b0eb2b02e4bd8123` |

## Context

Base crosswalk PREP (#206) mapped landed PREP packages to strategy DAG slots.
Honesty walls lived only as narrative non-claims. Sibling deepen packages now
carry explicit forbidden-action stubs; crosswalk still lacked that deepen card.

## Decision

Add deepen PREP under `docs/atlas-2.2/roadmap-crosswalk/` with:

1. Forbidden-action JSON Schema stub (not package data),
2. Negative rehearsal fixtures encoding expected rejections,
3. `INVARIANTS.md` freezing CROSSWALK ≠ UNLOCK / PREP ≠ PRODUCTION,

without relocating `CROSSWALK.md`, without editing harvest indexes, and without
unlocking runtime work.

## Consequences

- Traceability deepen is docs/fixtures/ADR + unit presence only.
- Unlock remains `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED=NO`.
- Release remains `ATLAS_2_1_RELEASE_CERTIFIED=NO`.
- Index rows for this deepen card are owned by a future README-INDEX harvest.

## Non-decisions

- Not refreshing `CROSSWALK.md` row inventory for wave-5/6 deepen packages
  (that remains a refresh protocol / harvest concern).
- Not promoting schemas into `src/project_atlas/schemas/`.
