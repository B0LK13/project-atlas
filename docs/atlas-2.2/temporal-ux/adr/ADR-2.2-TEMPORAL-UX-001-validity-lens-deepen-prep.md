# ADR-2.2-TEMPORAL-UX-001 — Validity / as-of UX deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b431494` |
| Tree | `26a59cd` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-2 temporal-ux PREP (PR #192) landed cockpit / validity-card / as-of-receipt
stubs and base negative sketches under `docs/atlas-2.2/temporal-ux/`. Sibling
deepen packages (compat-pin, conflict-ux, time-machine, mem-gov) carry an
explicit forbidden-action schema and deepen negatives with fixture-only
evidence walls. Temporal UX had invariants + mixed `temporal-action` kinds, but
lacked a dedicated forbidden-action enum and deepen package card.

## Decision

1. Land a docs-owned `forbidden-action.schema.json` with an enum action
   vocabulary under `docs/atlas-2.2/temporal-ux/contracts/`.
2. Add deepen negative fixtures that always set
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.
3. Keep base cockpit stubs, `temporal-action.schema.json`, and base negatives
   at their existing paths — no relocation or dual ownership.
4. Do **not** mutate `project_atlas.bitemporal` / `temporal_evaluator` or claim
   2.1 release / 2.2 unlock credit on this tip.

## Consequences

- Positive: temporal-ux reaches sibling deepen artifact depth; clear fail-closed
  vocabulary for future implementers distinct from the mixed action stub.
- Negative: no runtime temporal UX module until post-`v2.1.0` unlock; fixtures
  grant no gate credit.

## Non-decisions

- Exact web panel / Obsidian lens layout
- Whether silent-overlap cards deep-link into conflict-ux disposition
- Any change to AS-2.0-TEMPORAL-001 single-subject as-of semantics
