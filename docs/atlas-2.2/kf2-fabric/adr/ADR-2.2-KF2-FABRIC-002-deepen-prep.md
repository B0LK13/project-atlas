# ADR-2.2-KF2-FABRIC-002 — Estate KF fabric deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-KF2-FABRIC-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `7c2100d` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-2 KF2 fabric PREP (PR #186) landed estate inventory / projection stubs and
three base negatives under `docs/atlas-2.2/kf2-fabric/`. Wave-5 deepen peers
(conflict-ux / compat-pin / estate-ops) and fabric sibling XPROJ deepen (#233)
carry a dedicated forbidden-action schema plus deepen negatives with
fixture-only evidence walls. KF2 fabric lacked that sibling deepen depth.

## Decision

1. Land a docs-owned `kf2-fabric-forbidden-action.schema.json` with an enum
   action vocabulary under `docs/atlas-2.2/kf2-fabric/contracts/`.
2. Add deepen negative fixtures that always set
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.
3. Keep base inventory / projection stubs and base negatives at their existing
   paths — no relocation or dual ownership.
4. Do **not** mutate `kf2_fabric` / `kf2_inventory` until unlock.

## Consequences

- Positive: kf2-fabric reaches fabric-sibling deepen artifact depth; clear
  fail-closed vocabulary for future implementers.
- Negative: no runtime estate KF fabric module on this tip; fixtures grant no
  gate credit.

## Non-decisions

- Live emit wiring under `generated/kf2/` for multi-project rollups
- Whether estate projection schemas become package-data schemas post-unlock
- Multi-vault federation productization (`AS-2.0-FED-*` remains separate)

## Status

Accepted for PREP only. Unlock NO. `ATLAS_2_1_RELEASE_CERTIFIED=NO`.
Demo VERIFIED ≠ PILOT / ≠ release unlock.
