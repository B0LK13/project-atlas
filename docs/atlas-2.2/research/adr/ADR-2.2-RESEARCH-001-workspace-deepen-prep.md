# ADR-2.2-RESEARCH-001 — Research workspace deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-RESEARCH-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `d994953` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 research PREP (PR #171) landed pipeline stubs and positive fixtures under
shared `contracts/research/` and `fixtures/research/` paths. Ask Atlas 2 answer
lens deepen landed separately under `ask-atlas-2/` (PR #188). The base research
tree documented threat rows in `THREAT-ROWS.md` but lacked explicit invariants,
forbidden-action vocabulary, and negative rehearsal payloads at wave-2 sibling
depth.

## Decision

1. Land deepen invariants, forbidden-action schema, and negative fixtures under
   `docs/atlas-2.2/research/**` only (unique deepen path vs base stub tree).
2. Keep base stubs and positive fixtures at their existing shared paths — no
   relocation or dual ownership.
3. Forbid hypothesis promotion, silent conflict winners, LLM authority stamps,
   and evidence-class mismatch in the forbidden-action vocabulary.
4. Do **not** dual-own Ask Atlas 2 deepen stubs or mutate Core authority emit
   until unlock.

## Consequences

- Positive: research workspace reaches wave-2 sibling artifact depth; clear
  fail-closed vocabulary mapped to ADV threat rows.
- Negative: no runtime research module until post-`v2.1.0` unlock; fixtures
  grant no gate credit.

## Non-decisions

- CLI `atlas research …` command surface
- Hybrid retrieval plan integration defaults
- Automatic hypothesis ranking heuristics
