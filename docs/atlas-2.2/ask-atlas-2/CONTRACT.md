# Ask Atlas 2 deepen — contract stubs

Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/ask-atlas-2/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Stub inventory

| Stub file | Artifact | Operation |
|---|---|---|
| `ask2-deepen-answer-view.schema.json` | Deepened answer envelope | `project` |
| `ask2-citation-chain.schema.json` | Evidence→hypothesis→pack chain | `chain` |
| `ask2-lens-projection.schema.json` | Web / MCP / CLI lens view | `lens` |
| `ask2-forbidden-action.schema.json` | Fail-closed action proposal | `propose` |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `project` | `(pack_id)` | incomplete pack → `partial` with UNKNOWN density |
| `chain` | `(answer_id)` | missing evidence → empty chain + UNKNOWN facet |
| `lens` | `(surface)` | unknown surface → `rejected_malformed` |
| `propose` | `(action)` | reject live mutate / LLM authority / canonical write |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-ASK2-001 | Deepen view retains all eight research-ask2 answer fields |
| FR-2.2-ASK2-002 | Citation chain nodes bind evidence_id → hypothesis_id → pack_id |
| FR-2.2-ASK2-003 | Lens projections exist for web, mcp, and cli surfaces |
| FR-2.2-ASK2-004 | Empty EVIDENCE forces non-empty UNKNOWN (or explicit inability ANSWER) |
| FR-2.2-ASK2-005 | Forbidden actions reject live mutate, LLM authority, canonical write |
| FR-2.2-ASK2-006 | Envelopes set `authority.level=derived` and `live_path_owned=false` |
| NFR-2.2-ASK2-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-ASK2-002 | Prep stubs must not alter 2.1 runtime or mutate `ask_atlas_live.py` |
| NFR-2.2-ASK2-003 | Fixture success grants **no** PILOT / RELEASE / gate credit |

## Interaction with research-ask2

| Concern | Owner |
|---|---|
| Flat 8-field answer envelope | AS-2.2-RESEARCH-001 (`contracts/research/`) |
| Citation chains + multi-lens deepen | AS-2.2-ASK2-DEEPEN-PREP-001 (this PREP) |
| 2.1 LIVE_READ_ONLY match | `ask_atlas_live.py` — consume-only documentation link |

## Forbidden until unlock

- Importing these stubs from production modules
- Mutating `src/project_atlas/ask_atlas_live.py` from this lane
- Referencing stubs from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture answers
