# AS-2.2-COMPAT-PIN-PREP-001 — Compatibility anchor expectations (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-COMPAT-PIN-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-COMPAT-PIN-001` |
| Tip audited | `b201c823e311de96cfa8309487ca1947161d3a87` |
| Scope | `docs/atlas-2.2/compat-pin/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Reserve architecture, contract stubs, and fixture sketches for **Atlas 2.2
compatibility pinning** that declares how intelligence packages must bind to the
future **`v2.1.0` anchor** (`atlas-2.1.0-compat`) — using the certified
`AS-2.0-COMPAT-001` / `atlas-1.0.0-compat` pattern as a **read-only
conceptual reference** — without publishing a release anchor, without mutating
`compat_anchor.py`, and without claiming 2.1 release credit.

## Conceptual reference (read-only — AS-2.0-COMPAT-001)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| 1.0 anchor consumer | `AS-2.0-COMPAT-001` → `project_atlas.compat_anchor` | Established pin pattern (`atlas compat verify`) |
| 1.0 machine record | `docs/releases/1.0.0/compatibility-anchor.json` | Certified snapshot (`release_certified: true`) |
| 1.0 narrative | `docs/atlas-2.0/COMPATIBILITY.md` | Drift classes + non-negotiable invariants |
| 2.1 release path | `docs/atlas-2.1/` + `AS-REL-2.1` | Future anchor source (not yet certified) |
| Roadmap slot | `AS-2.2-COMPAT-PIN-001` in `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` | Post-unlock production path |

This PREP package **references** those contracts conceptually. It does **not**
ship `docs/releases/2.1.0/compatibility-anchor.json`, does **not** promote
stub schemas to package data, and does **not** dual-own `compat_anchor.py`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`README.md`](README.md) | Package index |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Anchor layers, drift classes, truth boundaries |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | Pin ≠ release / no invent anchor / 2.1 wins |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-COMPAT-PIN-001-2.1-anchor-prep.md`](adr/ADR-2.2-COMPAT-PIN-001-2.1-anchor-prep.md) | Prep boundary ADR |

## Hard invariants

1. **PREP PIN ≠ RELEASE ANCHOR** — fixtures declare future `atlas-2.1.0-compat`; no published 2.1 anchor on this tip.
2. **2.1 WINS CONFLICTS (post-cert only)** — until `ATLAS_2_1_RELEASE_CERTIFIED=YES`, 1.0 anchor remains the live consumer pin.
3. **FIXTURE REHEARSAL ≠ CERTIFICATION** — prep payloads set `release_certified: false` and `atlas_2_1_release_certified: false`.
4. **NO PILOT INVENT** — `pilot_roots = 0`, `invent_pilot_roots = false`, `authentic_estate = false`.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/compat_anchor.py`
- Not publication of `docs/releases/2.1.0/compatibility-anchor.json`
- Not shipped package-data schema promotion
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `v2.1.0` released / tagged on this tip
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or `docs/releases/2.1.0/`
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling 1.0 compat verify success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or set `release_certified: true` for 2.1

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock and anchor publication remain blocked until
`ATLAS_2_1_RELEASE_CERTIFIED=YES` and
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
