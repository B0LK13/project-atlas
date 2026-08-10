# ADR-2.2-DOD-002 — Definition-of-Done compiler deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-DOD-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `d994953` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 DoD compiler PREP (PR #170) landed Goal→proof chain stubs with PASS /
INCOMPLETE / FAIL(class mismatch) fixtures under shared `contracts/dod-compiler/`
and `fixtures/dod-compiler/` paths. Sibling wave-2 packages (Ask Atlas 2 deepen,
mem-gov deepen, conflict UX) carry explicit invariants, fixture-plan inventory,
and negative rehearsal payloads. DoD compiler lacked that sibling depth; FX-2.2-DOD-004
(unknown criterion binding) was listed but had no expected proof fixture.

## Decision

1. Land deepen invariants, forbidden-action schema, and negative fixtures under
   `docs/atlas-2.2/dod-compiler/**` only (unique deepen path vs base stub tree).
2. Keep base stubs and positive fixtures at their existing shared paths — no
   relocation or dual ownership.
3. Add `expected-proof-fail-unknown-criterion.json` to the shared fixture family
   for FX-2.2-DOD-004 without relocating base chain inputs.
4. Forbid Layer B promotion, LLM authority stamps, fixture-as-pilot, and invented
   PASS in the forbidden-action vocabulary.
5. Do **not** mutate Core authority emit or required CI gates until unlock.

## Consequences

- Positive: DoD compiler reaches wave-2 sibling artifact depth; clear fail-closed
  vocabulary for future implementers.
- Negative: no runtime DoD module until post-`v2.1.0` unlock; fixtures grant
  no gate credit.

## Non-decisions

- CLI `atlas dod …` surface shape
- Shipping JSON Schema as package data
- Automatic REL checklist assembly from proof alone
