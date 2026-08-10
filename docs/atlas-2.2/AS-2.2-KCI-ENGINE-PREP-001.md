# AS-2.2-KCI-ENGINE-PREP-001 — Knowledge CI engine (pre-v2.1.0 SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-KCI-ENGINE-PREP-001** |
| Alias / directive form | `AS-2.2-KCI-ENGINE-001 PREP` |
| Class | **PREP ONLY** (pre-unlock) |
| Unlock target | Post-`v2.1.0` → feeds `AS-2.2-KCI-001` (GAP-NS-005) |
| Tip audited | `f45134f356a5862e59c9d4c23daa50b912b85598` |
| Tree | `02eeb7392a7cfcbf78a8c28a2034cf0b54ac509e` |
| Evidence root | `D:\project-atlas-orphans\atlas-2.1-productionization-001\` |
| Coord cycle | `AS-COORD-CYCLE-2.1-011` READY_INDEPENDENT item 4 |
| Scope | `docs/atlas-2.2/**` only |
| Production mutation | **NONE** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** (blocked until `v2.1.0` cert) |

## Purpose

Reserve architecture, fixture families, and knowledge unit-test language for a
future **Knowledge CI engine** that deepens the 2.0 thin KCI contract + gate
catalog into an estate-scale, fail-closed evaluation surface — without touching
2.1 live production code, schemas shipped in package data, or Core authority.

## Baseline already on main (do not reimplement here)

| Surface | Package | Role |
|---|---|---|
| Thin compile request/receipt | `AS-2.0-KCI-001` | `project_atlas.kci` consume-only envelopes |
| Gate catalog harness | `AS-2.0-KCI-HARNESS-001` | `project_atlas.knowledge_ci_harness` |
| Schemas | `kci-compile-*`, `knowledge-ci-harness` | shipped package data |
| Gap row | `GAP-NS-005` | Priority P2; target `AS-2.2-KCI-001` |

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`kci-engine/ARCHITECTURE.md`](kci-engine/ARCHITECTURE.md) | Engine layers, truth boundaries, non-claims |
| [`kci-engine/UNIT-TEST-LANGUAGE.md`](kci-engine/UNIT-TEST-LANGUAGE.md) | Draft knowledge unit-test vocabulary |
| [`kci-engine/FIXTURE-PLAN.md`](kci-engine/FIXTURE-PLAN.md) | Fixture family reservation |
| [`fixtures/kci-engine/README.md`](fixtures/kci-engine/README.md) | Family inventory (sketched; payloads absent) |
| [`kci-engine/README.md`](kci-engine/README.md) | Package index |

## Explicit non-claims

- Not Layer B authority promotion
- Not silent authority-winner selection
- Not live CI runner / GitHub Actions job
- Not `AS-2.2-KCI-001` READY / IMPLEMENTATION
- Not authentic estate PILOT evidence
- Not a substitute for GAP-2.1-001..006

## Forbidden in this package

- Edits under `src/`, `apps/`, `tests/`, shipped `schemas/`
- Reopening `api_server`, `authz`, `ops_receipts`, `autonomy_l3`, Mission/Workspace pages
- Relabeling `AS-2.0-KCI-HARNESS-001` as 2.2 intelligence certified
- Fixture payloads that claim gate credit or PILOT PASS

## Exit (PREP)

PREP is complete when this tree lands on `main` via PR with docs-only diff and
honest non-claims. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
