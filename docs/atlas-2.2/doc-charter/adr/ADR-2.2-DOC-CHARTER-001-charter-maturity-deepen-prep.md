# ADR-2.2-DOC-CHARTER-001 — Charter + maturity matrix deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-DOC-CHARTER-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `1a69f49` |
| Tree | `bbf2a919` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-2 doc-charter PREP (PR #199) landed charter deepen, maturity-matrix draft,
row/matrix schema stubs, and base negative sketches under
`docs/atlas-2.2/doc-charter/`. Sibling deepen packages (compat-pin, temporal-ux,
estate-ops, chatgpt-live) carry an explicit forbidden-action schema and deepen
negatives with fixture-only evidence walls. Doc-charter had invariants + base
negatives, but lacked a dedicated forbidden-action enum and deepen package card.

## Decision

1. Land a docs-owned `doc-charter-forbidden-action.schema.json` with an enum
   action vocabulary under `docs/atlas-2.2/doc-charter/contracts/`.
2. Add deepen negative fixtures that always set
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.
3. Keep base matrix stubs, base negatives, and `CHARTER.md` deepen at their
   existing paths — no relocation or dual ownership.
4. Do **not** edit `docs/atlas-2.2/README.md`, mutate Core runtime paths, or
   claim 2.1 release / 2.2 unlock credit on this tip.

## Consequences

- Positive: doc-charter reaches sibling deepen artifact depth; clear fail-closed
  vocabulary for future implementers distinct from base negative envelopes.
- Negative: no production charter/matrix certification until post-`v2.1.0`
  unlock; fixtures grant no gate credit.

## Non-decisions

- Exact production matrix disposition vocabulary post-unlock
- Whether deepen forbidden kinds later promote into shipped package data
- Any change to 2.1 charter / matrix as authoritative certification surfaces
