# Cross-project fabric — contract stubs

Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/xproj/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced production gates.

Ship path after unlock (future): compose over existing
`src/project_atlas/schemas/xproj-*.schema.json` via ADR + freeze — do **not**
fork AS-XPROJ package_ids in this PREP.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `xproj-fabric-inventory.schema.json` | Estate fabric inventory envelope | `inventory` |
| `xproj-fabric-scenario.schema.json` | Scenario / substrate row | nested in inventory |
| `xproj-estate-lens.schema.json` | Read lens over selected buckets | `lens` |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `inventory` | `(scope, substrate_refs?)` | `rejected_malformed`, `quarantine_required`, empty buckets OK |
| `lens` | `(scope, buckets[])` | unknown bucket → reject; never invents entity/edge ids |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-XPROJ-001 | Fabric inventory cites AS-XPROJ-001..004 artifacts by id only |
| FR-2.2-XPROJ-002 | Inventory never mints global entities / edges / joins |
| FR-2.2-XPROJ-003 | Fuzzy / name-only / LLM join attempts quarantine (never merge) |
| FR-2.2-XPROJ-004 | Duplicate candidates retain `autocollapse: false` |
| FR-2.2-XPROJ-005 | Index / conflict refs never write `generated/indexes/` or Core claims |
| FR-2.2-XPROJ-006 | All fabric emits set `authority.level=derived` |
| NFR-2.2-XPROJ-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-XPROJ-002 | Prep stubs must not alter 2.1 runtime defaults or shipped schemas |
| NFR-2.2-XPROJ-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with AS-XPROJ-* (conceptual)

| Concern | Owner |
|---|---|
| Explicit entity/join registration | AS-XPROJ-001 (production on main) |
| Explicit cross-project edges | AS-XPROJ-002 (production on main) |
| Duplicate / successor candidates | AS-XPROJ-003 (production on main) |
| Derived indexes + conflict reports | AS-XPROJ-004 (production on main) |
| Estate fabric inventory / lens | AS-2.2-XPROJ-001 (this PREP → future) |

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture inventories
- Mutating `project_atlas.xproj_*` package_id / defaults from this lane
- Editing `docs/atlas-2.2/README.md` from this package
