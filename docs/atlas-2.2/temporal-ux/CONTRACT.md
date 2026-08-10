# Temporal UX — contract stubs

Package: **AS-2.2-TEMPORAL-UX-PREP-001**  
Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/temporal-ux/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `temporal-cockpit-view.schema.json` | Cockpit envelope | `list` / `panel` |
| `validity-window-card.schema.json` | Single validity-window card | `card` / nested in view |
| `as-of-lens-receipt.schema.json` | As-of lens receipt | `receipt` |
| `temporal-action.schema.json` | Operator action proposal | `propose` |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `panel` | `(scope, as_of_valid_time)` | empty OK; wall-clock → `rejected_malformed` |
| `card` | `(claim_id)` | `not_found`; never invents windows |
| `receipt` | `(scope, as_of_valid_time)` | `unresolved_overlap`; never silent pick |
| `propose` | `(action)` | reject wall-clock, silent winner, bitemporal mutation |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-TUX-001 | Cockpit lists validity-window cards bound to durable claim_id values |
| FR-2.2-TUX-002 | As-of lens receipt never accepts wall-clock `now` / `today` as *T* |
| FR-2.2-TUX-003 | Overlapping validity covers yield unresolved, not a silent winner |
| FR-2.2-TUX-004 | Temporal propose rejects wall-clock, silent_winner, bitemporal_mutation |
| FR-2.2-TUX-005 | UI / LLM outputs never write Layer B or mutate `bitemporal` runtime |
| FR-2.2-TUX-006 | Cockpit envelopes set `authority.level=derived` |
| NFR-2.2-TUX-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-TUX-002 | Prep stubs must not alter 2.1 runtime defaults or mutate `bitemporal` |
| NFR-2.2-TUX-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with AS-2.0-TEMPORAL-001 / TIME-MACHINE

| Concern | Owner |
|---|---|
| Single subject/field window + as-of result | AS-2.0-TEMPORAL-001 (`bitemporal`) — production on main |
| Multi-claim snapshot + T1–T2 diffs | AS-2.2-TIME-MACHINE-001 — soft peer docs |
| Validity UX cockpit + fail-closed operator actions | AS-2.2-TEMPORAL-001 (this PREP) |

## Forbidden until unlock

- Importing these stubs from production modules
- Mutating `src/project_atlas/bitemporal.py` from this lane
- Referencing stubs from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture cockpits

## Deepen PREP

See `AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md` and deepen negatives under `fixtures/`.
