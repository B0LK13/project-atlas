# AS-2.2-XPROJ-CONTRACT-PREP-001 — Cross-project fabric contracts (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-XPROJ-CONTRACT-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-XPROJ-001` estate fabric |
| Tip audited | `d62176967b6a946b97ee0b7fd0fe93d6938eeb09` |
| Tree | `8cc15dd54cee762eb7591719060e3a1310a1a895` |
| Scope | `docs/atlas-2.2/xproj/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for **Atlas 2.2
cross-project fabric intelligence** that consumes the certified AS-XPROJ-*
substrate (001–004) as **read-only conceptual references** — without mutating
`xproj_registry` / `xproj_edges` / `xproj_duplicates` / `xproj_indexes`
runtime modules, without elevating derived edges to authority, and without
claiming 2.1 release credit.

## Conceptual reference (read-only — AS-XPROJ-*)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Global entities | `AS-XPROJ-001` → `docs/AS-XPROJ-001-global-entities.md` | Explicit registry; name ≠ identity |
| Cross-project edges | `AS-XPROJ-002` → `docs/AS-XPROJ-002-cross-project-edges.md` | Explicit edges; Graph-003 ≠ XPROJ |
| Duplicate detection | `AS-XPROJ-003` → `docs/AS-XPROJ-003-duplicate-detection.md` | Candidates only; no autocollapse |
| Conflict indexes | `AS-XPROJ-004` → `docs/AS-XPROJ-004-conflict-indexes.md` | Derived indexes ≠ RET-001 / ≠ authority |
| Roadmap slot | `AS-2.2-XPROJ-001` in `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` | Post-unlock production path |

This PREP package **references** those contracts conceptually. It does **not**
re-ship their runtime schemas as package data and does **not** dual-own their
emit paths under `state/global-entities/` or `generated/xproj/`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`README.md`](README.md) | Package index |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, truth boundaries, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | Explicit / no-fuzzy / no-autocollapse / ≠ authority |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-XPROJ-001-cross-project-fabric-prep.md`](adr/ADR-2.2-XPROJ-001-cross-project-fabric-prep.md) | Prep boundary ADR |

## Hard invariants

1. **CROSS-PROJECT IDENTITY ≠ AUTOMATIC AUTHORITY** — registry / edges / indexes remain `authority.level = derived`.
2. **NAME / STRING ≠ IDENTITY** — no display-name, fuzzy, embedding, or LLM join.
3. **DUPLICATE CANDIDATE ≠ UUID COLLAPSE** — no autocollapse / no silent ingest skip.
4. **INDEXES ≠ AS-RET-001** — XPROJ indexes never write `generated/indexes/`.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/xproj_*.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not multi-vault federation productization (`AS-2.0-FED-*` remains separate)

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing XPROJ runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling AS-XPROJ fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or elevate derived fabric to Layer B

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
