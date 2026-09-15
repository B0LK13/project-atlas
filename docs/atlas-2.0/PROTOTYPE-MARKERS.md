# Atlas 2.0 — Prototype markers

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

Every artifact under `docs/atlas-2.0/` is **PROTOTYPE / PREP** until a
governor sets `ATLAS_2_0_IMPLEMENTATION_READY = YES` after 1.0 freeze
evidence. Markers below are inventory only — they do **not** authorize
production branches.

## Marker convention

| Marker | Meaning |
|---|---|
| **PROTOTYPE** | Design/docs sketch; may change without compat obligation |
| **PREP** | Track B deepen work; firewalled from `src/` |
| **READY=NO** | Explicit: not IMPLEMENTATION READY |

## Artifact inventory

| Artifact | Marker | Notes |
|---|---|---|
| `README.md` | PROTOTYPE / PREP | Prep tree index |
| `CHARTER.md` | PROTOTYPE / PREP | Purpose envelope; not certified |
| `VISION.md` | PROTOTYPE / PREP | Non-normative themes |
| `PRD.md` | PROTOTYPE / PREP | Placeholder FR catalog |
| `DAG.md` | PROTOTYPE / PREP | Gate chain sketch |
| `THREAT-MODEL.md` | PROTOTYPE / PREP | Threat register; mitigations = design intent |
| `PACKAGE-CONTRACT-STUBS.md` | PROTOTYPE / PREP | §98 name reservation + FR stubs |
| `COMPATIBILITY.md` | PROTOTYPE / PREP | Snapshot pin model sketch |
| `FIXTURE-PLAN.md` | PROTOTYPE / PREP | Fixture family names only |
| `fixtures/README.md` | PROTOTYPE / PREP | Docs-only inventory; no payloads |
| `OPENAI-MCP-DESIGN.md` | PROTOTYPE / PREP | No SDK/MCP production wiring |
| `OPEN-QUESTIONS.md` | PROTOTYPE / PREP | Research blockers; unanswered |
| `Z-WAVE-INDEX.md` | PROTOTYPE / PREP | Z1–Z14 lane map + status notes; all READY=NO |
| `PROTOTYPE-MARKERS.md` | PROTOTYPE / PREP | This file |
| `CONTRACT-FREEZE-CHECKLIST.md` | PROTOTYPE / PREP | §98 freeze checklist; all unchecked / NO |
| `prototypes/README.md` | PROTOTYPE / NON-PRODUCTION | Prototype stub index; not shippable |
| `prototypes/REVIEW-WALKTHROUGH-PROTOTYPE.md` | PROTOTYPE / NON-PRODUCTION | Human review walkthrough; no schema or executable artifact |
| `IMPLEMENTATION-READY-GATE.md` | PROTOTYPE / PREP | §56/§101 gate; READY=NO |

## Explicit non-claims

- `ATLAS_2_0_IMPLEMENTATION_READY = NO` (everywhere under this tree).
- No production schemas, CLI commands, or package-data contracts land from these markers.
- Prototype titles/headers must remain visible if artifacts are copied elsewhere.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial PROTOTYPE inventory for Track B Z-wave |
| 2026-08-09 | deepen-e: contract-freeze + prototypes/ stub inventory rows |
| 2026-08-09 | deepen-g: inventoried non-production review walkthrough; READY=NO |
