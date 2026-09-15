# ADR-2.2-TIME-MACHINE-001 — Knowledge Time Machine deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-TIME-MACHINE-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `961577c` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 time-machine PREP (PR #168) landed as-of / diff schema stubs and positive
fixtures under `docs/atlas-2.2/time-machine/`. Sibling wave-3 deepen packages
(mem-gov, research, DoD) carry explicit invariants, forbidden-action schemas,
and negative rehearsal payloads. Time Machine lacked that sibling depth.

Productionization evidence (`atlas-2.1-productionization-001`) reinforces that
**DEMO VERIFIED ≠ release certification** — fixture rehearsal must not stamp
`ATLAS_2_1_RELEASE_CERTIFIED`.

## Decision

1. Land deepen invariants, forbidden-action schema, and negative fixtures under
   `docs/atlas-2.2/time-machine/**` only (unique deepen path vs base stub tree).
2. Keep base positive fixtures and schema stubs at their existing paths — no
   relocation or dual ownership.
3. Forbid Layer B promotion, LLM authority stamps, silent overlap winners,
   wall-clock as-of, graph-as-authority, fixture-as-pilot, and release-cert
   stamps in the forbidden-action vocabulary.
4. Do **not** dual-own AS-2.0-TEMPORAL-001 single-subject as-of or mutate
   `bitemporal` runtime until unlock.

## Consequences

- Positive: time-machine reaches wave-3 sibling artifact depth; clear fail-closed
  vocabulary for future implementers.
- Negative: no runtime Time Machine module until post-`v2.1.0` unlock; fixtures
  grant no gate credit.

## Non-decisions

- Full bitemporal database / temporal SQL backend
- Ask Atlas 2 historical query planner wiring
- UI lens placement (owned by temporal-ux PREP peer)
