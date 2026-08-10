# AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001 — Temporal UX deepen (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-TEMPORAL-001` |
| Tip audited | `b431494dc8860f4f1db3f327c9ccf991699ccfc5` |
| Tree | `26a59cd76bd9df410912b4552ddd907f7a160588` |
| Scope | `docs/atlas-2.2/temporal-ux/**` deepen lane (+ unique unit test) |
| Production mutation | **NONE** |
| `bitemporal` / Layer B | **do not mutate** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Deepen the wave-2 Temporal UX PREP **beyond** the base cockpit / validity-card /
as-of-receipt stubs already landed under `docs/atlas-2.2/temporal-ux/` (PR
[#192](https://github.com/B0LK13/project-atlas/pull/192)).

This PREP owns a **unique deepen path** under `docs/atlas-2.2/temporal-ux/**` for:

- explicit fail-closed forbidden-action vocabulary (wall-clock as-of, silent
  winner, bitemporal mutation, LLM authority, UI canonical write, PILOT invent,
  release-cert stamp),
- negative rehearsal payloads that document expected rejections with
  fixture-only evidence walls,
- a deepen ADR that freezes the PREP ≠ RUNTIME MUTATION boundary,

without mutating `project_atlas.bitemporal`, without dual-owning Time Machine
stubs, and without claiming 2.1 release credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Base Temporal UX PREP | `AS-2.2-TEMPORAL-UX-PREP-001` → `temporal-ux/` | Cockpit + card + receipt stubs (peer; do not dual-own) |
| Base action stub | `contracts/temporal-action.schema.json` | Mixed allowed/forbidden ops (peer) |
| Base negatives | `fixtures/negative-*.expect.json` | Base rejection sketches (peer) |
| Time Machine deepen | `AS-2.2-TIME-MACHINE-DEEPEN-PREP-001` | As-of/diff forbidden vocab (peer; do not dual-own) |
| Temporal substrate | AS-2.0-TEMPORAL-001 / `bitemporal` | Single subject/field as-of (peer) |
| Future slot | `AS-2.2-TEMPORAL-001` | Post-unlock production path |

This PREP package **references** those contracts conceptually. It does **not**
relocate base stubs, does **not** dual-own the shared fixture family, and does
**not** edit `src/project_atlas/**`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Validity lens layers (peer to base PREP) |
| [`CONTRACT.md`](CONTRACT.md) | Base stub index (peer) |
| [`INVARIANTS.md`](INVARIANTS.md) | UI≠canonical / no wall-clock / no silent winner |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Base + deepen fixture inventory (peer) |
| [`contracts/forbidden-action.schema.json`](contracts/forbidden-action.schema.json) | Forbidden-action JSON Schema stub (enum) |
| [`fixtures/`](fixtures/) | Deepen negative rehearsal payloads |
| [`adr/ADR-2.2-TEMPORAL-UX-001-validity-lens-deepen-prep.md`](adr/ADR-2.2-TEMPORAL-UX-001-validity-lens-deepen-prep.md) | Deepen boundary ADR |

Base package card remains
[`AS-2.2-TEMPORAL-UX-PREP-001.md`](AS-2.2-TEMPORAL-UX-PREP-001.md). Index
ownership stays with the 2.2 prep-index lane; this deepen card is the deepen
entry. **No `README.md`** in this tree.

## Deepen delta vs base temporal-ux PREP

| Concern | base temporal-ux (#192) | This deepen PREP |
|---|---|---|
| Cockpit + card + receipt stubs | Four schemas under `contracts/` | Peer reference only |
| Mixed action stub | `temporal-action.schema.json` | Peer; not relocated |
| Base negatives | Wall-clock / silent winner / bitemporal | Peer; not relocated |
| Fail-closed ops | Truth-boundary + mixed action kinds | Dedicated forbidden-action enum + deepen negatives |
| Honesty walls | Embedded in cockpit samples | Required `evidence_class` / `authentic_estate` / `release_certified` / `pilot_pass` / `canonical_writes` |
| Deepen ADR | — | Explicit deepen boundary ADR |

## Hard invariants

1. **UI ≠ CANONICAL** — temporal UX panels never write Layer B or mutate windows.
2. **NO WALL-CLOCK NOW** — `now` / `today` rejected as as-of / valid-time input.
3. **NO SILENT WINNER** — overlapping covers stay unresolved; no auto-pick.
4. **NO BITEMPORAL RUNTIME MUTATION** — do not edit `project_atlas.bitemporal`.
5. **LLM ≠ AUTHORITY** — no LLM-suggested as-of winner / trust score.
6. **NO 2.1 RELEASE STAMP** — `release_certified=false`, `pilot_pass=false`.
7. **NO PILOT INVENT** — `authentic_estate=false`, `evidence_class=fixture-only`.
8. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE
   CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/bitemporal.py` or `temporal_evaluator.py`
- Not shipped package-data schema promotion
- Not dual-ownership of Time Machine stubs or AS-2.0-TEMPORAL-001
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not relocation of base cockpit stubs or base negatives

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or Core bitemporal runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling base fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots or set `release_certified=true` /
  `pilot_pass=true` / `canonical_writes=true` / `authentic_estate=true`

## Exit (PREP)

PREP is complete when this deepen tree lands via PR with docs/fixtures/ADR +
unit presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
