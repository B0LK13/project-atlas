# AS-2.2-KF2-FABRIC-PREP-001 — Estate KF fabric contracts (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-KF2-FABRIC-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` → feeds future `AS-2.2-KF2-FABRIC-001` |
| Tip audited | `4cd646a46be16b29db9cdaeb3e965530b2c4bea9` |
| Scope | `docs/atlas-2.2/kf2-fabric/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** (still the post-`v2.1.0` unlock gate) |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for **Atlas 2.2
estate-scale Knowledge Fabric inventory / projection** that consumes the
certified AS-KF2-* substrate (NS / ENTITY / REL / inventory export) as
**read-only conceptual references** — without mutating `kf2_fabric` /
`kf2_inventory` runtime modules, without elevating derived fabric rows to
authority, without `cross_promote=true`, and without claiming 2.1 release
credit.

## Conceptual reference (read-only — AS-KF2-*)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Namespace | `AS-KF2-NS-001` → `docs/AS-KF2-WAVE1.md` | Explicit NS rows under `generated/kf2/namespaces/` |
| Entity | `AS-KF2-ENTITY-001` → Wave 1 | Explicit entity rows; optional XPROJ id cite ≠ authority |
| Relationship | `AS-KF2-REL-001` → Wave 1 | Explicit relationship rows; Graph≠authority |
| Inventory export | `AS-KF2-002` → `docs/AS-KF2-002.md` | Derived counts; `cross_promote=false` |
| Roadmap slot | `AS-2.2-KF2-FABRIC-001` in `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` | Post-unlock production path |

This PREP package **references** those contracts conceptually. It does **not**
re-ship their runtime schemas as package data and does **not** dual-own their
emit paths under `generated/kf2/` or `generated/ops/kf2/`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`README.md`](README.md) | Package index |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, truth boundaries, non-claims |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | KF2 ≠ authority / no cross-promote / ≠ Layer B |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-KF2-FABRIC-001-estate-fabric-prep.md`](adr/ADR-2.2-KF2-FABRIC-001-estate-fabric-prep.md) | Prep boundary ADR |

## Hard invariants

1. **KF2 FABRIC ≠ AUTHORITY** — namespace / entity / relationship / inventory remain `authority.level = derived`.
2. **CROSS PROMOTE = FALSE** — estate projection never promotes KF2 rows into Layer B claims.
3. **INVENTORY ≠ PILOT / RELEASE** — count envelopes are fabric accounting only.
4. **PROJECTION ≠ MUTATION** — estate projection cites ids only; never writes `generated/kf2/`.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/kf2_fabric.py` / `kf2_inventory.py`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (unlock remains that gate after `v2.1.0`)
- Not authentic estate PILOT evidence
- Not multi-vault federation productization (`AS-2.0-FED-*` remains separate)
- Not dual-ownership of AS-XPROJ / AS-GRAPH emit trees

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or existing KF2 runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling AS-KF2 fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or set `cross_promote: true`

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0`.
