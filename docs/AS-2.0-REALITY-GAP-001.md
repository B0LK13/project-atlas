# AS-2.0-REALITY-GAP-001 — Reality-gap fixture inventory

| Field | Value |
|---|---|
| Package | **AS-2.0-REALITY-GAP-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (fixtures + schema) |
| Class | **READY** — fixtures only |
| Compat | `atlas-1.0.0-compat` |

## Purpose

Ship a deterministic, schema-validated inventory of the gaps named in
`docs/atlas-2.0/REALITY-GAP.md`. Evidence class is always **fixture-only**.

## Surfaces

| Surface | Path |
|---|---|
| Schema | `reality-gap-inventory` |
| Module | `project_atlas.reality_gap` |
| Fixtures | `docs/atlas-2.0/fixtures/reality-gap/` |
| Vault output | `generated/ops/reality-gap-inventory.json` |

## Canonical scenarios

| gap_id | Blocker class |
|---|---|
| `estate-twin` | blocked-pilot |
| `agent-os-in-core` | partially-addressed |
| `federation` | partially-addressed |
| `advanced-ux` | partially-addressed |
| `production-sync` | blocked-pilot |
| `provider-mcp` | partially-addressed |

## Invariants

- `pilot_roots = 0`
- `authentic_estate = false` per scenario
- `invent_pilot_roots = false` (const)
- Does not stamp WEB ACCEPTED / RELEASE / 2.0 READY
- Bound to compatibility anchor

## Non-claims

- Not authentic estate PILOT
- Not Digital Twin production (AS-2.0-TWIN-001 remains BLOCKED)
- Not SYNC v2 final
