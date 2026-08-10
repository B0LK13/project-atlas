# ChatGPT Live — contract stubs

Status: **PREP ONLY**. JSON Schema files under
`docs/atlas-2.2/chatgpt-live/contracts/` are **documentation stubs**, not
installed via `importlib.resources`, not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

## Stub inventory

| Stub file | Artifact | Operation | Owner |
|---|---|---|---|
| `live-bridge-request.schema.json` | Opt-in live request | `request` | base PREP |
| `quarantine-envelope.schema.json` | Mandatory quarantine result | `quarantine` | base PREP |
| `live-session-receipt.schema.json` | Derived session receipt | `receipt` | base PREP |
| `forbidden-action.schema.json` | Base fail-closed action proposal | `reject` | base PREP |
| `chatgpt-live-deepen-forbidden-action.schema.json` | Deepen fail-closed vocabulary | `reject` | deepen PREP |

## Conceptual operations

| Op | Signature (sketch) | Fail-closed outcomes |
|---|---|---|
| `request` | `(opt_in, session_id)` | `rejected_disabled` when opt-in false; malformed → `rejected_malformed` |
| `quarantine` | `(envelope_id, payload)` | secret → `rejected-secret`; never skip quarantine |
| `receipt` | `(session_id)` | requires quarantine ref; never Layer B |
| `reject` (base) | `(action)` | reject bypass / Layer B write / LLM authority / default-on live / pilot invent |
| `reject` (deepen) | `(action)` | reject env force-live / billing without opt-in / quarantine bypass / release-cert stamp |

## FR stubs (planning IDs only — not certified requirements)

| ID | Requirement stub |
|---|---|
| FR-2.2-CGL-001 | Live bridge is opt-in; default path remains export-only |
| FR-2.2-CGL-002 | Every accepted live payload is written through provider quarantine first |
| FR-2.2-CGL-003 | Session receipts set `authority.level=derived` and `llm_authority=false` |
| FR-2.2-CGL-004 | Bypass-quarantine / Layer B write / LLM authority stamps are rejected |
| FR-2.2-CGL-005 | Live bridge never mutates `chatgpt_bridge` export semantics in PREP |
| FR-2.2-CGL-006 | Fixtures set `pilot_roots=0` and never invent PILOT estate roots |
| FR-2.2-CGL-007 | Env vars alone must not force `live_chatgpt_api` (deepen) |
| FR-2.2-CGL-008 | Billing / paid live spend requires explicit `opt_in` (deepen) |
| FR-2.2-CGL-009 | Fixture success must not stamp release certification (deepen) |
| NFR-2.2-CGL-001 | Deterministic serialization (`sort_keys=True`; no `generated.at`) |
| NFR-2.2-CGL-002 | Prep stubs must not alter 2.1 runtime defaults or mutate `chatgpt_bridge` |
| NFR-2.2-CGL-003 | Fixture success grants **no** PILOT / RELEASE / gate credit; DEMO ≠ RELEASE |

## Interaction with AS-2.1-CHATGPT-BRIDGE-001

| Concern | Owner |
|---|---|
| On-disk export → quarantine + bridge receipt | AS-2.1-CHATGPT-BRIDGE-001 (`chatgpt_bridge`) — production on main |
| Optional live API → quarantine-first session | AS-2.2-CHATGPT-LIVE-001 (this PREP) |
| Fixture capture with live API forbidden | AS-2.0-CHATGPT-CAPTURE-001 — soft peer; do not dual-own |

## Forbidden until unlock

- Importing these stubs from production modules
- Mutating `src/project_atlas/chatgpt_bridge.py` from this lane
- Referencing stubs from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture live sessions
