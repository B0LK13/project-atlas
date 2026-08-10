# Knowledge Fabric estate — contract stubs

Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/kf2-fabric/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced production gates.

Ship path after unlock (future): compose over existing
`src/project_atlas/schemas/kf2-*.schema.json` via ADR + freeze — do **not**
fork AS-KF2 package_ids in this PREP.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `kf2-estate-fabric-inventory.schema.json` | Estate KF fabric inventory envelope | `inventory` |
| `kf2-estate-fabric-scenario.schema.json` | Scenario / substrate row | nested in inventory |
| `kf2-estate-projection.schema.json` | Read projection over selected buckets | `project` |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `inventory` | `(scope, substrate_refs?)` | `rejected_malformed`, `quarantine_required`, empty buckets OK |
| `project` | `(scope, buckets[])` | unknown bucket → reject; never invents KF ids; never writes emit trees |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-KF2-001 | Fabric inventory cites AS-KF2-NS/ENTITY/REL/002 artifacts by id only |
| FR-2.2-KF2-002 | Inventory never mints namespaces / entities / relationships |
| FR-2.2-KF2-003 | All fabric emits keep `cross_promote = false` |
| FR-2.2-KF2-004 | Projection never writes `generated/kf2/` or `generated/ops/kf2/` |
| FR-2.2-KF2-005 | Authority elevate / Layer B promote attempts quarantine |
| FR-2.2-KF2-006 | All fabric emits set `authority.level=derived` |
| NFR-2.2-KF2-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-KF2-002 | Prep stubs must not alter 2.1 runtime defaults or shipped schemas |
| NFR-2.2-KF2-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with AS-KF2-* (conceptual)

| Concern | Owner |
|---|---|
| Namespace rows | AS-KF2-NS-001 (production on main) |
| Entity rows | AS-KF2-ENTITY-001 (production on main) |
| Relationship rows | AS-KF2-REL-001 (production on main) |
| Count inventory export | AS-KF2-002 (production on main) |
| Estate fabric inventory / projection | AS-2.2-KF2-FABRIC-001 (this PREP → future) |

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture inventories
- Mutating `project_atlas.kf2_*` package_id / defaults from this lane
- Editing `docs/atlas-2.2/README.md` from this package
