# AS-2.2-DOC-CHARTER-PREP-001 — Charter + maturity matrix (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-DOC-CHARTER-PREP-001** |
| Class | **PREP ONLY** (charter deepen / matrix draft / contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-DOC-CHARTER-001` |
| Tip audited | `bbbdc12` (post #198) |
| Scope | `docs/atlas-2.2/CHARTER.md`, `docs/atlas-2.2/doc-charter/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Deepen the Atlas 2.2 prep **charter** and reserve a **maturity matrix draft**
that inventories landed PREP packages with normative maturity classes — using
Atlas 2.1 `CHARTER.md` and `FEATURE-MATURITY-MATRIX.md` as **read-only
conceptual references** — without stamping release credit, without mutating
runtime modules, and without claiming authentic estate PILOT evidence.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| 2.1 charter | `docs/atlas-2.1/CHARTER.md` | Maturity vocabulary + non-goals pattern |
| 2.1 matrix | `docs/atlas-2.1/FEATURE-MATURITY-MATRIX.md` | Row layout + disposition column |
| 2.2 prep index | `docs/atlas-2.2/README.md` | Landed PREP package inventory (read-only; do not edit) |
| 2.2 strategy DAG | `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` | `AS-2.2-DOC-CHARTER-001` first READY slot |
| Shallow charter (prior) | `docs/atlas-2.2/CHARTER.md` | Deepened by this PREP |
| Roadmap slot | `AS-2.2-DOC-CHARTER-001` | Post-unlock production charter refresh |

This PREP package **references** those surfaces conceptually. It does **not**
re-ship 2.1 matrix rows as authoritative 2.2 certification and does **not**
dual-own `docs/atlas-2.2/README.md`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`../CHARTER.md`](../CHARTER.md) | Deepened 2.2 prep charter (goals, vocabulary, DAG, gates) |
| [`FEATURE-MATURITY-MATRIX.md`](FEATURE-MATURITY-MATRIX.md) | Draft matrix for landed PREP packages |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Charter layers, matrix posture, truth boundaries |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | PREP≠cert / no PILOT invent / no runtime mutation |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-DOC-CHARTER-001-charter-maturity-prep.md`](adr/ADR-2.2-DOC-CHARTER-001-charter-maturity-prep.md) | Prep boundary ADR |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).

## Hard invariants

1. **PREP MATRIX ≠ RELEASE CERTIFICATION** — draft rows do not stamp 2.1/2.2 release credit.
2. **NO PILOT INVENT** — `pilot_roots = 0`, `authentic_estate = false` on all prep fixtures.
3. **NO RUNTIME MUTATION** — do not edit `src/`, shipped schemas, or `apps/` in this PREP.
4. **LLM ≠ AUTHORITY** — matrix dispositions are audit labels, not subjective trust scores.
5. **UI ≠ CANONICAL · Unknown ≠ healthy** — carried from 2.1 charter; applies to all 2.2 PREP.
6. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not `v2.1.0` / `v2.2.0` released or tagged on this tip
- Not authentic estate PILOT evidence
- Not production mutation of Core intelligence paths
- Not shipped package-data schema promotion

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or runtime intelligence modules
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling PREP fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or set release-certified flags

## Exit (PREP)

PREP is complete when the deepened charter and this tree land via PR with
docs/fixtures/ADR + unit presence tests only. Production charter refresh
(`AS-2.2-DOC-CHARTER-001`) remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
