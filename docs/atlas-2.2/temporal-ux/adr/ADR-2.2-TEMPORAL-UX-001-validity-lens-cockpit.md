# ADR-2.2-TEMPORAL-UX-001 — Validity / as-of UX lens (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-TEMPORAL-UX-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b5d8729` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

GAP-NS-003 calls for temporal / bitemporal claim validity UX on the 2.2
north-star path. Core already ships fail-closed valid-time windows and as-of
selection (AS-2.0-TEMPORAL-001 / `bitemporal`), and Time Machine PREP reserves
multi-claim snapshot + diff stubs. Pre-unlock work must not mutate that
runtime while still landing reviewable UX contracts.

## Decision

1. Land cockpit architecture, JSON Schema stubs, and fixtures under
   `docs/atlas-2.2/temporal-ux/**` only.
2. Treat `project_atlas.bitemporal` as **consume-only** until
   `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Forbid wall-clock as-of inputs, silent winners on overlap, UI canonical
   writes, and bitemporal runtime mutation in the temporal-action vocabulary.
4. Do **not** mutate runtime `bitemporal` in this PREP PR.
5. Do **not** edit `docs/atlas-2.2/README.md` (index owned elsewhere).

## Consequences

- Positive: parallel-safe prep; clear fail-closed action wall; gap register
  package has an owned doc surface distinct from Time Machine stubs.
- Negative: no live temporal UX until post-`v2.1.0` unlock; fixtures grant no
  gate credit.

## Non-decisions

- Exact Mission/Workspace panel layout
- Whether Ask Atlas 2 embeds receipts vs deep-links
- Any change to Core temporal evaluator defaults
