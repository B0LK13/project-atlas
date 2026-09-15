# ADR-2.2-ESTATE-OPS-001 — Estate operations deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-ESTATE-OPS-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b431494` |
| Tree | `26a59cd` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-2 estate-ops PREP (PR #197) landed cockpit / lens / receipt stubs and base
action negatives under `docs/atlas-2.2/estate-ops/`. Sibling deepen packages
carry a dedicated forbidden-action schema plus deepen negatives with
fixture-only evidence walls. Estate-ops lacked that sibling depth (base
`estate-ops-action` remains a peer action stub, not the deepen forbidden-action
card).

## Decision

1. Land a docs-owned `estate-ops-forbidden-action.schema.json` with an enum
   action vocabulary under `docs/atlas-2.2/estate-ops/contracts/`.
2. Add deepen negative fixtures that always set
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.
3. Keep base cockpit stubs and base action negatives at their existing paths —
   no relocation or dual ownership of `estate-ops-action.schema.json`.
4. Do **not** mutate `ops_health` / `ops_events` or `apps/web` until unlock.

## Consequences

- Positive: estate-ops reaches sibling deepen artifact depth; clear fail-closed
  vocabulary for future implementers.
- Negative: no runtime estate cockpit module on this tip; fixtures grant no
  gate credit.

## Non-decisions

- Live MCP `atlas.ops.health.read` wiring for multi-project rollups
- Mission Control / Workspace panel composition under `apps/web`
- Whether ops receipts become package-data schemas post-unlock
