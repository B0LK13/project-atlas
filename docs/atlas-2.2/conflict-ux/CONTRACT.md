# Conflict UX — contract stubs

Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/conflict-ux/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `conflict-cockpit-view.schema.json` | Cockpit envelope | `list` |
| `conflict-projection-card.schema.json` | Single conflict card | `card` / nested in view |
| `review-queue-slice.schema.json` | CONFLICT queue slice | `queue` |
| `disposition-action.schema.json` | Operator action proposal | `propose` |
| `conflict-ux-forbidden-action.schema.json` | Deepen forbidden-action vocabulary | `reject` (DEEPEN; do not relocate disposition) |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `list` | `(scope)` | empty OK; malformed scope → `rejected_malformed` |
| `card` | `(conflict_id)` | `not_found`; never invents sides |
| `queue` | `(scope)` | same durable review root; no second queue invent |
| `propose` | `(action)` | reject `auto_resolve` / UI writes / authority elevation |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-CUX-001 | Cockpit lists conflict cards bound to durable conflict_id values |
| FR-2.2-CUX-002 | Cards expose duplicate-source facet only when ≥2 distinct source_ids |
| FR-2.2-CUX-003 | Review-queue slice reuses CONFLICT category; no second durable root |
| FR-2.2-CUX-004 | Disposition propose rejects auto-resolve and silent winner picks |
| FR-2.2-CUX-005 | UI / LLM outputs never write Layer B or elevate authority.level |
| FR-2.2-CUX-006 | Cockpit envelopes set `authority.level=derived` |
| NFR-2.2-CUX-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-CUX-002 | Prep stubs must not alter 2.1 runtime defaults or mutate `conflict_projections` |
| NFR-2.2-CUX-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with AS-CORE2-008

| Concern | Owner |
|---|---|
| Duplicate-source facet + review reason hardening | AS-CORE2-008 (`conflict_projections`) — production on main |
| Cockpit view model + fail-closed operator actions | AS-2.2-CONFLICT-UX-001 (this PREP) |
| Cross-project conflict reports | AS-XPROJ-004 — soft peer; do not dual-own |

## Forbidden until unlock

- Importing these stubs from production modules
- Mutating `src/project_atlas/conflict_projections.py` from this lane
- Referencing stubs from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture cockpits
