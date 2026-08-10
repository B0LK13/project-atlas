# AS-2.2-TEMPORAL-UX-PREP-001 — Validity / bitemporal UX lens (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-TEMPORAL-UX-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-TEMPORAL-001` |
| Tip audited | `b5d8729b57f06fdd719ee7d3786b62dc9b54e094` |
| Gap | `GAP-NS-003` (temporal / bitemporal claim validity UX) |
| Scope | `docs/atlas-2.2/temporal-ux/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for an Atlas 2.2
**validity-window + as-of / diff UX lens** that consumes AS-2.0-TEMPORAL-001
and AS-2.2-TIME-MACHINE-001 as **read-only conceptual references** — without
mutating `project_atlas.bitemporal`, without inventing wall-clock `now` as
valid-time, and without claiming 2.1 release credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Valid-time windows + as-of | `AS-2.0-TEMPORAL-001` → `project_atlas.bitemporal` | Single subject/field selection semantics |
| Time Machine + Diff stubs | `AS-2.2-TIME-MACHINE-001` → `docs/atlas-2.2/time-machine/` | Multi-claim snapshot + T1–T2 envelopes |
| Claims / authority | `AS-CORE-003` / `AS-CORE-005` | Evidence-backed claim substrate |
| Roadmap slot | `AS-2.2-TEMPORAL-001` in strategy roadmap | Post-unlock production path (UX receipts) |
| Soft peer | `AS-2.2-CONFLICT-UX-PREP-001` | Overlap / unresolved remains visible |

This PREP package **references** those contracts conceptually. It does **not**
re-ship Core bitemporal schemas as package data and does **not** dual-own
`project_atlas.bitemporal` / `temporal_evaluator` emit paths.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, truth boundaries, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | UI≠canonical / no wall-clock / no silent winner |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-TEMPORAL-UX-001-validity-lens-cockpit.md`](adr/ADR-2.2-TEMPORAL-UX-001-validity-lens-cockpit.md) | Prep boundary ADR |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).

## Hard invariants

1. **UI ≠ CANONICAL** — temporal UX panels never write Layer B claims or mutate windows.
2. **NO WALL-CLOCK NOW** — `now` / `today` are never accepted as as-of / valid-time inputs.
3. **NO SILENT WINNER** — overlapping validity covers stay unresolved; no auto-pick.
4. **NO BITEMPORAL RUNTIME MUTATION** — do not edit `project_atlas.bitemporal` in this PREP.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/bitemporal.py` or `temporal_evaluator.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not a second Time Machine product root (consume `time-machine/` contracts)

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing bitemporal runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling Time Machine fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots, wall-clock as-of, or silent winners

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
