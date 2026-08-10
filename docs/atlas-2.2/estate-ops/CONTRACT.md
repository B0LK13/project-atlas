# Estate Ops — contract stubs

Package: **AS-2.2-ESTATE-OPS-PREP-001**  
Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/estate-ops/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `estate-ops-cockpit-view.schema.json` | Cockpit envelope | `panel` / `list` |
| `mission-control-lens.schema.json` | Mission Control lens card | `lens` |
| `ops-health-receipt.schema.json` | Ops health receipt at estate scope | `receipt` |
| `estate-ops-action.schema.json` | Operator action proposal | `propose` |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `panel` | `(estate_scope, lens_ids[])` | partial OK; missing evidence → unknown chips |
| `lens` | `(project_id, lens_kind)` | `not_found`; never invents queue items |
| `receipt` | `(estate_scope)` | rollup unknown when signals absent; never healthy invent |
| `propose` | `(action)` | reject canonical_write, pilot_invent, unknown_as_healthy |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-EO-001 | Cockpit binds Mission Control / Workspace / Ops Health lens cards |
| FR-2.2-EO-002 | Ops health rollup never maps unknown signals to healthy |
| FR-2.2-EO-003 | Estate scope consumes XPROJ cited_ids; never elevates fabric to Layer B |
| FR-2.2-EO-004 | EstateOpsAction rejects canonical_write, pilot_invent, unknown_as_healthy |
| FR-2.2-EO-005 | UI / LLM outputs never write Layer B or mutate ops_health runtime |
| FR-2.2-EO-006 | Cockpit envelopes set `authority.level=derived` |
| NFR-2.2-EO-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-EO-002 | Prep stubs must not alter 2.1 runtime defaults or mutate ops modules |
| NFR-2.2-EO-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with AS-OBS-001 / XPROJ / WEB lenses

| Concern | Owner |
|---|---|
| Health snapshot + rollup | AS-OBS-001 (`ops_health`) — production on main |
| Cross-project estate scope | AS-2.2-XPROJ-001 — soft peer docs |
| Web route lenses (MC/WS/Ops) | AS-WEB-* — read-only stubs |
| Estate ops cockpit + fail-closed actions | AS-2.2-ESTATE-OPS-001 (this PREP) |

## Forbidden until unlock

- Importing these stubs from production modules
- Mutating `src/project_atlas/ops_health.py` from this lane
- Referencing stubs from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture cockpits
