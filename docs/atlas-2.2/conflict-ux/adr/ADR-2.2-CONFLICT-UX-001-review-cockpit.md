# ADR-2.2-CONFLICT-UX-001 — Conflict review cockpit (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-CONFLICT-UX-PREP-001 |
| Date | 2026-08-10 |
| Tip | `d621769` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

GAP-NS-004 calls for a conflict projection + review cockpit on the 2.2
north-star path. Core already ships conflict records and
`conflict_projections` honesty helpers (AS-CORE2-008). Pre-unlock work must
not mutate that runtime while still landing reviewable contracts.

## Decision

1. Land cockpit architecture, JSON Schema stubs, and fixtures under
   `docs/atlas-2.2/conflict-ux/**` only.
2. Treat `project_atlas.conflict_projections` as **consume-only** until
   `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Forbid auto-resolve, UI canonical writes, LLM winner picks, and
   authority elevation in the disposition-action vocabulary.
4. Do **not** mutate runtime `conflict_projections` in this PREP PR.

## Consequences

- Positive: parallel-safe prep; clear fail-closed action wall; gap register
  package has an owned doc surface.
- Negative: no live cockpit until post-`v2.1.0` unlock; fixtures grant no
  gate credit.

## Non-decisions

- Exact Mission/Workspace panel layout
- Whether Ask Atlas 2 embeds cards vs deep-links
- Any change to ConflictType enums
