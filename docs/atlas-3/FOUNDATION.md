# Atlas 3.0 — Foundation convergence

| Field | Value |
|---|---|
| Directive | D-193 |
| Status | **FOUNDATION CONVERGENCE** |
| Base program | D-191 / D-192 (`docs/atlas-3/NORTH-STAR.md`) |
| `FULL_LIVE_DEMO_READY` | **NO** |
| `MERGE_AUTHORIZATION` | **NOT_GRANTED** |
| Chronicle | **ROADMAP_HORIZON** — design notes only |

## Priority packages

```text
AT3-001 NORTH STAR 3.0
AT3-002 PROJECT TWIN SCHEMA
AT3-003 ENGINEERING EVENT MODEL
AT3-004 CAPABILITY REGISTRY
AT3-005 2.x→3.x COMPATIBILITY CONTRACT
AT3-014 UNIVERSAL EVENT LEDGER
AT3-015 ATLAS PULSE
AT3-030 ATLAS START
AT3-035 UNIVERSAL LLM CONNECTOR FRAMEWORK
AT3-050 AGENT PROOF-OF-WORK FOUNDATION
```

Everything else is downstream. Chronicle / Ambient Knowledge is
`ROADMAP_HORIZON` (`docs/atlas-3/chronicle/HORIZON.md`).

## Layer ownership (no duplicate engines)

| Layer | Owner | Must not duplicate |
|---|---|---|
| Evidence | Layer A + AT3-014 ledger + quarantine | Second source-hash engine |
| Truth | Truth Core (`knowledge_compiler`) | Atlas 3 writers to Layer B |
| Time | AS-2.0-TEMPORAL-001 / kdiff | Second clock / wall-clock valid-time |
| Causality | Twin `CAUSED_BY` (derived) | Graph winners |
| Intent | Decisions + memory intent (non-canonical) | Collapsing intent into current state |
| Proof | AT3-050 AGENT_PROOF | Model self-certification |
| Autonomy | Orch DAG / leases / owner gates | Self-merge |

```text
NO duplicated truth engines
NO duplicated temporal engines
NO duplicated identity systems
NO duplicated provenance systems
```

## Hard dependency chain

```text
AT3-001 → AT3-002 → AT3-003 → AT3-014 → AT3-015
Parallel after stable contracts: AT3-030 · AT3-035 · AT3-050
AT3-004 and AT3-005 run from the start (registry + compatibility).
```

Do not jump to Chronicle, Organization Twin, Simulation, Marketplace, or
Enterprise SaaS before this foundation converges.

## Exit criteria

Foundation is READY only when all of the following are true **as isolated
Atlas 3 contracts** (certified 2.x surfaces remain untouched while
`FULL_LIVE_DEMO_READY = NO`):

| Criterion | Artifact |
|---|---|
| NORTH_STAR coherent | `NORTH-STAR.md` + this file |
| PROJECT_TWIN_SCHEMA stable | `contracts/twin-*.schema.json` + `atlas3/twin.py` |
| ENGINEERING_EVENT_SCHEMA stable | `contracts/engineering-event.schema.json` + `events.py` |
| EVENT_LEDGER_CONTRACT stable | `ledger.py` (evidence, not Truth Core) |
| CAPABILITY_REGISTRY stable | `atlas3/capabilities.py` |
| COMPATIBILITY_PLAN proven | `atlas3/compat.py` |
| SECURITY_MODEL reviewed | `SECURITY.md` + `atlas3/security.py` |
| PULSE_SPEC implementation-ready | AT3-015 eight questions |
| START_SPEC implementation-ready | budget + freshness |
| LLM_CONNECTOR_FRAMEWORK implementation-ready | AT3-035 substrate only |
| PROOF_OF_WORK implementation-ready | AT3-050 foundation |

Runtime remains additive under `src/project_atlas/atlas3/`.
Demo closure wins on overlap.

## Reuse map

```text
REUSED_COMPONENTS =
  Truth Core, project identity, bitemporal/kdiff, conversation_capture,
  chatgpt_bridge (compose), Knowledge Inbox, provider quarantine,
  Context Compiler, orch owner gates, AS-GRAPH-003 aliases

NEW_COMPONENTS =
  twin schema, canonical event envelope, capability registry,
  compatibility prover, Pulse attention question, Start freshness

MIGRATION_REQUIRED = NO for 2.x vaults
COMPATIBILITY_RISK = LOW if isolated; HIGH if certified surfaces change
```
