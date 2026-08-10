# AS-2.2-INTEL-SLICE-PREP-001 — Estate intelligence slice (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-INTEL-SLICE-PREP-001** |
| Class | **PREP ONLY** (architecture / fixtures) |
| Unlock target | Post-`v2.1.0` → `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` → feeds future `AS-2.2-INTEL-SLICE-001` |
| Tip audited | `f73c4de4fc5cb123a9198eca84e203f651bfb664` |
| Scope | `docs/atlas-2.2/intel-slice/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve **architecture sketches and fixture payloads** for an Atlas 2.2
**estate intelligence slice** — a deterministic, derived envelope that
composes read-only citations from KF fabric, hybrid retrieval / context packs,
temporal validity, and conflict-projection surfaces for Ask / MCP / Estate-Ops /
UI consumers — without mutating Core authority, without elevating derived ranks,
and without claiming 2.1 release credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Roadmap consumer slot | `AS-2.2-INTEL-SLICE-001` in `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` | Post-unlock production path |
| KF fabric | `AS-2.2-KF2-FABRIC-001` / PREP sibling | Estate inventory / projection citations |
| Hybrid + context | `AS-2.2-RET-CTX-001` (feeds from `AS-2.2-RET-HYBRID-001`) | Retrieval / context-pack citations |
| Temporal | `AS-2.2-TEMPORAL-001` / TEMPORAL-UX PREP | Validity-window / unknown citations |
| Conflict UX | `AS-2.2-CONFLICT-UX-001` / CONFLICT-UX PREP | Open conflict / review citations |
| Soft consumer | Ask Atlas 2 / Estate-Ops / MCP lenses | Consume-only slice readers |

This PREP package **references** those lanes conceptually. It does **not**
dual-own their emit trees, does **not** ship runtime modules, and does **not**
promote derived slice rows to Layer B authority.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, composition, truth boundaries |
| [`INVARIANTS.md`](INVARIANTS.md) | Slice ≠ authority / no silent resolve / no unlock flip |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).  
**No contracts / ADR / runtime** in this package — architecture + fixtures only.

## Hard invariants

1. **INTEL SLICE ≠ AUTHORITY** — envelope `authority.level = derived` always.
2. **COMPOSITION ≠ MUTATION** — cites upstream ids only; never writes Layer B / KF / review roots.
3. **NO SILENT CONFLICT WINNER** — open conflicts remain visible in the slice.
4. **LLM ≠ AUTHORITY** — model output never stamps canonical or authority elevation.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/`, `apps/`, `api_server`, or `mcp_server`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not dual-ownership of KF2 / RET / TEMPORAL / CONFLICT-UX emit paths

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing Core runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Adding `README.md` under `intel-slice/`
- Relabeling fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots, silent winners, or `authority.level` above `derived`

## Exit (PREP)

PREP is complete when this tree lands via PR with architecture + fixtures + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0`.
