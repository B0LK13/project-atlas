# AS-2.2-CHATGPT-LIVE-PREP-001 — Live ChatGPT API bridge (quarantine-first SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-CHATGPT-LIVE-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds optional `AS-2.2-CHATGPT-LIVE-001` |
| Gap | `GAP-NS-007` (Live ChatGPT API bridge, quarantine-first) |
| Tip audited | `b5d8729b57f06fdd719ee7d3786b62dc9b54e094` |
| Tree | `3e5bdb983a2729eb3343db208648c66e90a53d99` |
| Scope | `docs/atlas-2.2/chatgpt-live/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for an Atlas 2.2
**optional live ChatGPT API bridge** that is **quarantine-first**: every live
payload lands in PROV/provider quarantine before any operator review, and never
becomes Layer B authority. This PREP does **not** mutate
`project_atlas.chatgpt_bridge`, does **not** flip `live_chatgpt_api` defaults,
and does **not** claim 2.1 release or PILOT credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Export bridge | `AS-2.1-CHATGPT-BRIDGE-001` → `chatgpt_bridge.py` | On-disk export → quarantine; `live_chatgpt_api=false` |
| Capture receipt | `AS-2.0-CHATGPT-CAPTURE-001` → `chatgpt_capture.py` | Fixture capture; `live_api` forbidden |
| Provider quarantine | `provider_adapters.quarantine_provider_output` | Shared quarantine envelope path |
| Roadmap slot | `AS-2.2-CHATGPT-LIVE-001` (optional) | Post-unlock production path |
| Gap register | `GAP-NS-007` | Live API absent; export-path today |

This PREP package **references** those contracts conceptually. It does **not**
re-ship bridge schemas as package data and does **not** dual-own
`generated/ops/chatgpt/` emit paths.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, quarantine-first flow, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | Quarantine wall / LLM≠authority / no default-on live |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-CHATGPT-LIVE-001-quarantine-first-live-bridge-prep.md`](adr/ADR-2.2-CHATGPT-LIVE-001-quarantine-first-live-bridge-prep.md) | Prep boundary ADR |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).

## Hard invariants

1. **QUARANTINE-FIRST** — live API payloads never skip provider/PROV quarantine.
2. **LLM ≠ AUTHORITY** — live turns never stamp Layer B or elevate `authority.level`.
3. **LIVE DEFAULT OFF** — `live_chatgpt_api` remains opt-in; export bridge stays default path.
4. **NO `chatgpt_bridge` MUTATION** — this PREP must not edit `src/project_atlas/chatgpt_bridge.py`.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/chatgpt_bridge.py` or `chatgpt_capture.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not a default-on live ChatGPT network client

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing chatgpt runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling export-bridge fixture success as live-API or 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots, bypass quarantine, or stamp LLM authority

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
