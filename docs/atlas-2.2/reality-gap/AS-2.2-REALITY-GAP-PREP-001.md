# AS-2.2-REALITY-GAP-PREP-001 — Reality Gap (pre-v2.1.0 SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-REALITY-GAP-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future Reality Gap intelligence surfaces |
| Tip audited | `a1e0972a18608487f71c6979e454247df52d2e44` |
| Tree | `c6cfe95ffe7d3c1699459f620aadf112c66a8524` |
| Scope | `docs/atlas-2.2/reality-gap/**` (+ optional ADR-028 + unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for a **2.2 Reality
Gap** inventory that deepens the 2.0 fixture catalog
(`docs/AS-2.0-REALITY-GAP-001.md` / `docs/atlas-2.0/REALITY-GAP.md`) into an
estate-honest gap register — without touching shipped `reality_gap` /
`reality_gap_ui` runtime packages or inventing PILOT roots.

## Conceptual reference (read-only)

| Surface | Package / path | Role |
|---|---|---|
| Inventory module | `AS-2.0-REALITY-GAP-001` → `project_atlas.reality_gap` | Fixture inventory (do not mutate here) |
| UI catalog | `AS-2.0-REALITY-GAP-UI-001` → `project_atlas.reality_gap_ui` | Read-only panels; UI ≠ canonical |
| Narrative | `docs/atlas-2.0/REALITY-GAP.md` | Six canonical gap rows |
| Fixtures | `docs/atlas-2.0/fixtures/reality-gap/` | 2.0 sample inventory |

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`README.md`](README.md) | Package index |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, truth boundaries, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | unknown≠healthy / UI≠canonical / no PILOT invent |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| `docs/adr/ADR-028-reality-gap-prep.md` | Prep boundary ADR |

## Hard invariants

1. **unknown ≠ healthy** — missing / unresolved / unknown status never maps to healthy, PASS, or READY.
2. **UI ≠ canonical** — Reality Gap UI panels never write Layer B or stamp release credit.
3. **no PILOT invent** — `pilot_roots = 0`, `invent_pilot_roots = false`, `authentic_estate = false` on all prep fixtures.
4. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/reality_gap.py` or `reality_gap_ui.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not Digital Twin / SYNC v2 / Agent OS production certification

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing 2.0 reality-gap runtime paths
- Relabeling 2.0 fixture inventory success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or treat unknown as healthy

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
