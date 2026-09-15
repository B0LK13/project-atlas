# AS-2.2-ADV-POOL-001 — ADV matrix pool (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-ADV-POOL-001** |
| Class | **DOCUMENTATION_ONLY / THREAT_MATRIX_SKETCH** |
| Status | **PREP** (SAFE pre-`v2.1.0`) |
| Baseline | MAIN `80ab762` / TREE `cfc667a` (post-#173 tip) |
| Sole-writer surface | `docs/atlas-2.2/adv-pool/**` (+ optional ADR-031, presence test) |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Hold an **additive** adversarial / fail-closed threat-matrix sketch for the
Atlas 2.2 P1 prep surfaces (RET / CTX / MEM / KCI / DoD / TIME / REALITY /
RESEARCH) **without** reopening landed 2.1 Host/CORS / L3 / ops-receipt ADV
rows (`#154` / `#155`) and **without** mutating `docs/atlas-2.1/ADV-LIVE-SUITE.md`.

## Tree

| Path | Role |
|---|---|
| [ADV-MATRIX.md](ADV-MATRIX.md) | Threat rows per 2.2 prep surface |
| [FIXTURE-INVARIANTS.md](FIXTURE-INVARIANTS.md) | Fixture / secret / authority invariants |
| [fixtures/README.md](fixtures/README.md) | Synthetic fixture policy (no secret material) |

## Explicit non-claims

- Not a rewrite or deepen of landed 2.1 ADV-LIVE-SUITE rows
- Not runtime / `src/` / web / PILOT authentication work
- Not RELEASE / PILOT / intelligence-unlock certification
- Not authority elevation via retrieval, context packs, memory, KCI, or LLM

## Relation to sibling prep packages

Sibling sole-writer dirs (`ret-hybrid/`, `ctx-compiler/`, `mem-gov/`,
`kci-engine/`, `dod-compiler/`, `time-machine/`, `reality-live/`,
`reality-gap/`, `research/`) own their architecture and contracts. This
pool catalogs **cross-cutting ADV expectations** those packages must
eventually satisfy after `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.

**Does not edit** `docs/atlas-2.2/README.md` (H02 prep-index sole-writer).
