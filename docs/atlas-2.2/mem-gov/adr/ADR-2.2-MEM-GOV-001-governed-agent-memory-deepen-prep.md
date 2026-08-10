# ADR-2.2-MEM-GOV-001 — Governed agent memory deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-MEM-GOV-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `d994953` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 mem-gov PREP (PR #169) landed record and axis stubs with positive
fixtures under shared `contracts/mem-gov/` and `fixtures/mem-gov/` paths.
Sibling wave-2 packages (conflict UX, Ask Atlas 2 deepen, intel slice) carry
explicit invariants, fixture-plan inventory, and negative rehearsal payloads.
Mem-gov lacked that sibling depth.

## Decision

1. Land deepen invariants, forbidden-action schema, and negative fixtures under
   `docs/atlas-2.2/mem-gov/**` only (unique deepen path vs base stub tree).
2. Keep base stubs and positive fixtures at their existing shared paths — no
   relocation or dual ownership.
3. Forbid Layer B promotion, LLM authority stamps, and dual-active forks in the
   forbidden-action vocabulary.
4. Do **not** dual-own AS-INT-011 receipt revocation indexes or mutate Core
   authority emit until unlock.

## Consequences

- Positive: mem-gov reaches wave-2 sibling artifact depth; clear fail-closed
  vocabulary for future implementers.
- Negative: no runtime memory module until post-`v2.1.0` unlock; fixtures grant
  no gate credit.

## Non-decisions

- Storage layout under `generated/ops/` vs control-plane spool
- Vector / embedding memory backends
- Automatic compaction of expired records
