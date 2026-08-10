# Reality Gap — contract stubs index

Status: **PREP ONLY**. These JSON files are **documentation stubs**, not
installed package schemas and not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

| Stub file | Artifact | Role |
|---|---|---|
| `reality-gap-prep-inventory.schema.json` | Inventory envelope | Package + scenarios + invariants |
| `reality-gap-prep-scenario.schema.json` | Scenario row | Single gap_id row with fail-closed flags |

## FR stubs (planning IDs only)

| ID | Requirement stub |
|---|---|
| FR-2.2-RG-001 | Inventory enumerates documented gap_ids without inventing estate |
| FR-2.2-RG-002 | Scenario status `unknown` never maps to healthy / READY / PASS |
| FR-2.2-RG-003 | UI catalog remains read-only (`canonical_writes=false`) |
| FR-2.2-RG-004 | `pilot_roots=0` and `invent_pilot_roots=false` on all prep fixtures |
| FR-2.2-RG-005 | Prep fixtures cannot stamp WEB ACCEPTED / RELEASE / 2.1 CERTIFIED |
| NFR-2.2-RG-001 | Deterministic inventory serialization (`sort_keys`, no wall-clock) |
| NFR-2.2-RG-002 | Prep stubs must not alter 2.1 runtime defaults or mutate 2.0 modules |

## Compatibility posture

- Stubs live under `docs/atlas-2.2/reality-gap/contracts/` only.
- Future production schemas will pin a 2.1 compatibility snapshot (not invented here).
- Until unlock: treat these as review vocabulary only.
- `authority.level` on the inventory envelope remains `derived`.

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED / PILOT PASS from fixture inventory alone
