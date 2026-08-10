# ADR-2.2-ASK2-001 — Ask Atlas 2 answer lens deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-ASK2-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `4cd646a` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Research-ask2 already sketches a flat Ask Atlas 2 answer envelope under
`docs/atlas-2.2/research/` and `contracts/research/`. Operators still need
citation-chain depth, multi-lens projections, and an explicit fail-closed wall
against live-path mutation and LLM authority — without editing
`ask_atlas_live.py` pre-unlock.

## Decision

1. Land deepen architecture, JSON Schema stubs, and fixtures under
   `docs/atlas-2.2/ask-atlas-2/**` only (unique path vs research-ask2).
2. Treat `project_atlas.ask_atlas_live` as **consume-only / do not mutate**
   until `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Forbid live mutate, LLM authority stamps, and canonical writes in the
   forbidden-action vocabulary.
4. Do **not** dual-own or relocate research-ask2 stubs.

## Consequences

- Positive: parallel-safe deepen prep; clear live-path wall; research peer
  remains intact.
- Negative: no live deepen lenses until post-`v2.1.0` unlock; fixtures grant
  no gate credit.

## Non-decisions

- Exact web panel / MCP tool layout
- Whether citation chains embed conflict cards vs deep-links
- Any change to 2.1 LIVE_READ_ONLY match semantics
