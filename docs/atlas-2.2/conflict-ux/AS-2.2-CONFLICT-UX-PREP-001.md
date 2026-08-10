# AS-2.2-CONFLICT-UX-PREP-001 — Conflict projection cockpit (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-CONFLICT-UX-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-CONFLICT-UX-001` |
| Tip audited | `d62176967b6a946b97ee0b7fd0fe93d6938eeb09` |
| Tree | `8cc15dd54cee762eb7591719060e3a1310a1a895` |
| Scope | `docs/atlas-2.2/conflict-ux/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for an Atlas 2.2
**conflict projection + review cockpit** that consumes the certified
AS-CORE-003 / AS-CORE2-008 conflict and review spine as **read-only
conceptual references** — without mutating `conflict_projections`, without
inventing a second review-queue root, and without claiming 2.1 release credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Claims / conflicts | `AS-CORE-003` → `docs/claims-authority-conflicts.md` | Material conflict records + review emit |
| Conflict projections | `AS-CORE2-008` → `project_atlas.conflict_projections` | Duplicate-source facets + review honesty |
| Durable review roots | `review/conflicts/`, `review/pending/` | Single queue roots (do not fork) |
| Lexical companions | `generated/indexes/conflicts.json`, `reviews.json` | Additive indexes ≠ second queue |
| Roadmap slot | `AS-2.2-CONFLICT-UX-001` in strategy roadmap | Post-unlock production path |
| Soft consumer | `AS-2.2-RESEARCH-001` Ask Atlas 2 | Conflict-presence in answers |

This PREP package **references** those contracts conceptually. It does **not**
re-ship Core conflict schemas as package data and does **not** dual-own
`review/` or `generated/indexes/` emit paths.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, truth boundaries, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | UI≠canonical / no silent resolve / one queue |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-CONFLICT-UX-001-conflict-projection-cockpit-prep.md`](adr/ADR-2.2-CONFLICT-UX-001-conflict-projection-cockpit-prep.md) | Prep boundary ADR |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).

## Hard invariants

1. **UI ≠ CANONICAL** — cockpit panels never write Layer B claims or resolve conflicts.
2. **NO SILENT RESOLVE** — unresolved conflicts remain visible; no auto-winner.
3. **GRAPH ≠ CONFLICT INVENTION** — Graph edges never mint Core conflict records.
4. **ONE REVIEW QUEUE ROOT** — no second durable queue beside `review/conflicts/` / `review/pending/`.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/conflict_projections.py` or `knowledge_compiler.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not a second review-queue product root

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing conflict runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling AS-CORE2-008 fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots, silent winners, or Graph-minted conflicts

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
