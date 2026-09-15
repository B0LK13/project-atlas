# Knowledge Time Machine — contract stubs

Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/time-machine/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `as-of-snapshot.schema.json` | As-of estate/subject slice | `as_of` |
| `knowledge-diff.schema.json` | T1→T2 envelope | `diff` |
| `claim-diff.schema.json` | Claim delta block | nested in knowledge-diff |
| `graph-diff.schema.json` | Graph delta block | nested in knowledge-diff |
| `decision-diff.schema.json` | Decision/review delta block | nested in knowledge-diff |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `as_of` | `(scope, as_of_valid_time, knowledge_compilation_id?)` | `unresolved_overlap`, `unresolved_incomplete`, `rejected_malformed`, `not_found` |
| `diff` | `(scope, t1, t2, knowledge_compilation_id?)` | empty delta OK; malformed range rejected; never invents adds |

`t1` / `t2` are declared valid-time markers. If `t2` < `t1` lexically after
normalization → `rejected_malformed` (no silent swap).

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-TM-001 | As-of returns a deterministic snapshot bound to declared valid-time *T* |
| FR-2.2-TM-002 | As-of never accepts wall-clock `now` / `today` as *T* |
| FR-2.2-TM-003 | Overlapping validity covers yield unresolved, not a silent winner |
| FR-2.2-TM-004 | Diff emits claim, graph, and decision delta blocks for the same scope |
| FR-2.2-TM-005 | Diff units cite claim_id / entity_id / decision_id; no fabricated ids |
| FR-2.2-TM-006 | Graph and decision diffs set `authority.level=derived` |
| NFR-2.2-TM-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-TM-002 | Prep stubs must not alter 2.1 runtime defaults or shipped schemas |
| NFR-2.2-TM-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with AS-2.0-TEMPORAL-001

| Concern | Owner |
|---|---|
| Single subject/field window + as-of result | AS-2.0-TEMPORAL-001 (production on main) |
| Multi-claim snapshot + T1–T2 diffs | AS-2.2-TIME-MACHINE-001 (this PREP) |
| Claim Identity v2 | Unchanged — temporal metadata out of identity inputs |

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture snapshots
- Mutating `project_atlas.bitemporal` package_id / defaults from this lane
