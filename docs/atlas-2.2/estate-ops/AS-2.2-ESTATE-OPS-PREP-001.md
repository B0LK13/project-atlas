# AS-2.2-ESTATE-OPS-PREP-001 — Estate operations lens (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-ESTATE-OPS-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-ESTATE-OPS-001` |
| Tip audited | `b201c823e311de96cfa8309487ca1947161d3a87` |
| Scope | `docs/atlas-2.2/estate-ops/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for an Atlas 2.2
**estate operations cockpit** (Mission Control · Workspace · Ops Health at
multi-project scope) that consumes AS-OBS-001, AS-XPROJ-*, and certified 2.1 web
lenses as **read-only conceptual references** — without mutating
`ops_health` / `ops_events` runtime modules, without elevating UI receipts to
Layer B authority, and without claiming 2.1 release credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Ops health snapshot | `AS-OBS-001` → `project_atlas.ops_health` | unknown≠healthy rollup semantics |
| Ops events / receipts | `AS-OBS-002` / `AS-OBS-003` → `ops_events` | Receipt micro-lens substrate |
| Cross-project fabric | `AS-2.2-XPROJ-001` → `docs/atlas-2.2/xproj/` | Estate slice scope + cited_ids |
| Mission Control lens | `AS-WEB-MISSION-CONTROL-001` → `apps/web` route `#/mission-control` | Read-only; UI≠canonical |
| Workspace lens | `AS-WEB-WORKSPACE-001` → `#/workspace` | Read-only work queue projection |
| Ops Health lens | `AS-WEB-OPS-HEALTH-001` → `#/ops` | Receipt micro-lens; honest unknown |
| MCP read surface | `atlas.ops.health.read` | Consume-only estate health read |
| Roadmap slot | `AS-2.2-ESTATE-OPS-001` in strategy roadmap | Post-unlock production path |

This PREP package **references** those contracts conceptually. It does **not**
re-ship Core ops schemas as package data and does **not** dual-own
`project_atlas.ops_health` / `ops_events` emit paths or web lens stubs under
`apps/web/public/`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, truth boundaries, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | unknown≠healthy / UI≠canonical / no PILOT invent |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-ESTATE-OPS-001-estate-ops-lens-prep.md`](adr/ADR-2.2-ESTATE-OPS-001-estate-ops-lens-prep.md) | Prep boundary ADR |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).

## Hard invariants

1. **unknown ≠ healthy** — missing / unresolved ops evidence never maps to healthy, PASS, or READY rollup.
2. **UI ≠ canonical** — Mission Control / Workspace / Ops Health panels never write Layer B or stamp release credit.
3. **LLM ≠ authority** — derived envelopes only; no subjective trust scores.
4. **no PILOT invent** — `pilot_roots = 0`, `authentic_estate = false` on all prep fixtures.
5. **NO OPS RUNTIME MUTATION** — do not edit `project_atlas.ops_health` / `ops_events` in this PREP.
6. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/ops_health.py` or `ops_events.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not live OAI / ChatGPT bridge productization
- Not release cert or pilot waiver language

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing ops runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling DEMO_FIXTURE estate smoke success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or treat unknown as healthy

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
