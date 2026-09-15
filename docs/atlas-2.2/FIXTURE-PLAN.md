# Atlas 2.2 — Fixture plan (Hybrid Retrieval PREP)

Status: **PREP ONLY** — sketches under `docs/atlas-2.2/fixtures/`.
Not production schemas. Not CI harness credit. Not PILOT.

## Families

| Family | Path | Purpose | Mutates vault? |
|---|---|---|---|
| hybrid-retrieval | `fixtures/hybrid-retrieval/` | Plan samples + semantic-disabled expectations | **no** |
| (reserved) semantic-index-spike | `fixtures/semantic-index-spike/` | Future isolated vector spike inputs | **no** |
| (reserved) fusion-eval | `fixtures/fusion-eval/` | Multi-slot fusion golden sketches | **no** |

## Inventory ledger

| Scenario | ID | Positive | Negative | Payloads | Runner | Gate credit |
|---|---|---|---|---|---|---|
| Exact lexical plan shape | FX-2.2-RET-001 | sketched + sample | n/a | present (docs) | absent | **NO** |
| Prefix lexical plan shape | FX-2.2-RET-002 | sketched + sample | n/a | present (docs) | absent | **NO** |
| Semantic disabled / reject | FX-2.2-RET-003 | disabled slot | enable fails closed | present (docs) | absent | **NO** |
| Fusion order sketch | FX-2.2-RET-004 | prose + JSON sketch | semantic cannot erase lexical | present (docs) | absent | **NO** |

## Creation policy

- Docs-only paths; do **not** import from `src/project_atlas/` or wire CI yet.
- Synthetic IDs and relative paths only; no host roots; no secrets.
- When post-unlock production opens, fixtures may promote to `fixtures/atlas-2.2/` with entry-gate approval.

## Cross-links

- Architecture: [HYBRID-RETRIEVAL-2.md](HYBRID-RETRIEVAL-2.md)
- Benchmarks: [benchmarks/README.md](benchmarks/README.md)
- Predecessor: [docs/AS-2.0-RET-HYBRID-001.md](../AS-2.0-RET-HYBRID-001.md)


## Deepen-wave fixture rollup (AS-2.2-PREP-FIXTURE-ROLLUP-001)

Status: **PREP ONLY** index of package-owned deepen negatives.
Fixtures stay under each package tree — **do not relocate / do not dual-own**.
Cut tip: MAIN `8c48bb3` / TREE `da63619` (full `8c48bb309f70eb4be46a12214eb44de52586b11d` / `da636190e55af7fa8821556088f841a5973d9e28`).
`ATLAS_2_1_RELEASE_CERTIFIED=NO`. Unlock NO. Demo VERIFIED ≠ release / ≠ PILOT.

| Package | Card | Deepen fixtures (reference) | Forbidden-action schema |
|---|---|---|---|
| `AS-2.2-ASK2-DEEPEN-PREP-001` | [ask-atlas-2/AS-2.2-ASK2-DEEPEN-PREP-001.md](ask-atlas-2/AS-2.2-ASK2-DEEPEN-PREP-001.md) | `ask-atlas-2/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `ask2-forbidden-action.schema.json` |
| `AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001` | [chatgpt-live/AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001.md](chatgpt-live/AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001.md) | `chatgpt-live/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `chatgpt-live-deepen-forbidden-action.schema.json`, `forbidden-action.schema.json` |
| `AS-2.2-COMPAT-PIN-DEEPEN-PREP-001` | [compat-pin/AS-2.2-COMPAT-PIN-DEEPEN-PREP-001.md](compat-pin/AS-2.2-COMPAT-PIN-DEEPEN-PREP-001.md) | `compat-pin/fixtures/` (5 deepen negatives) | `compat-pin-forbidden-action.schema.json` |
| `AS-2.2-CONFLICT-UX-DEEPEN-PREP-001` | [conflict-ux/AS-2.2-CONFLICT-UX-DEEPEN-PREP-001.md](conflict-ux/AS-2.2-CONFLICT-UX-DEEPEN-PREP-001.md) | `conflict-ux/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `conflict-ux-forbidden-action.schema.json` |
| `AS-2.2-CTX-DEEPEN-PREP-001` | [ctx-compiler/AS-2.2-CTX-DEEPEN-PREP-001.md](ctx-compiler/AS-2.2-CTX-DEEPEN-PREP-001.md) | `ctx-compiler/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `ctx-forbidden-action.schema.json` |
| `AS-2.2-DOC-CHARTER-DEEPEN-PREP-001` | [doc-charter/AS-2.2-DOC-CHARTER-DEEPEN-PREP-001.md](doc-charter/AS-2.2-DOC-CHARTER-DEEPEN-PREP-001.md) | `doc-charter/fixtures/` (6 deepen negatives) | `doc-charter-forbidden-action.schema.json` |
| `AS-2.2-DOD-DEEPEN-PREP-001` | [dod-compiler/AS-2.2-DOD-DEEPEN-PREP-001.md](dod-compiler/AS-2.2-DOD-DEEPEN-PREP-001.md) | `dod-compiler/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `dod-forbidden-action.schema.json` |
| `AS-2.2-ESTATE-OPS-DEEPEN-PREP-001` | [estate-ops/AS-2.2-ESTATE-OPS-DEEPEN-PREP-001.md](estate-ops/AS-2.2-ESTATE-OPS-DEEPEN-PREP-001.md) | `estate-ops/fixtures/` (5 deepen negatives) | `estate-ops-forbidden-action.schema.json` |
| `AS-2.2-INTEL-SLICE-DEEPEN-PREP-001` | [intel-slice/AS-2.2-INTEL-SLICE-DEEPEN-PREP-001.md](intel-slice/AS-2.2-INTEL-SLICE-DEEPEN-PREP-001.md) | `intel-slice/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `intel-slice-forbidden-action.schema.json` |
| `AS-2.2-KCI-ENGINE-DEEPEN-PREP-001` | [kci-engine/AS-2.2-KCI-ENGINE-DEEPEN-PREP-001.md](kci-engine/AS-2.2-KCI-ENGINE-DEEPEN-PREP-001.md) | `kci-engine/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `kci-forbidden-action.schema.json` |
| `AS-2.2-KF2-FABRIC-DEEPEN-PREP-001` | [kf2-fabric/AS-2.2-KF2-FABRIC-DEEPEN-PREP-001.md](kf2-fabric/AS-2.2-KF2-FABRIC-DEEPEN-PREP-001.md) | `kf2-fabric/fixtures/` (8 deepen negatives) | `kf2-fabric-forbidden-action.schema.json` |
| `AS-2.2-MEM-GOV-DEEPEN-PREP-001` | [mem-gov/AS-2.2-MEM-GOV-DEEPEN-PREP-001.md](mem-gov/AS-2.2-MEM-GOV-DEEPEN-PREP-001.md) | `mem-gov/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `mem-gov-forbidden-action.schema.json` |
| `AS-2.2-REALITY-GAP-DEEPEN-PREP-001` | [reality-gap/AS-2.2-REALITY-GAP-DEEPEN-PREP-001.md](reality-gap/AS-2.2-REALITY-GAP-DEEPEN-PREP-001.md) | `reality-gap/fixtures/` (7 deepen negatives) | `reality-gap-forbidden-action.schema.json` |
| `AS-2.2-REALITY-LIVE-DEEPEN-PREP-001` | [reality-live/AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md](reality-live/AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md) | `reality-live/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `reality-live-forbidden-action.schema.json` |
| `AS-2.2-RESEARCH-DEEPEN-PREP-001` | [research/AS-2.2-RESEARCH-DEEPEN-PREP-001.md](research/AS-2.2-RESEARCH-DEEPEN-PREP-001.md) | `research/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `research-forbidden-action.schema.json` |
| `AS-2.2-RET-HYBRID-DEEPEN-PREP-001` | [ret-hybrid/AS-2.2-RET-HYBRID-DEEPEN-PREP-001.md](ret-hybrid/AS-2.2-RET-HYBRID-DEEPEN-PREP-001.md) | `ret-hybrid/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `ret-hybrid-forbidden-action.schema.json` |
| `AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001` | [roadmap-crosswalk/AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001.md](roadmap-crosswalk/AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001.md) | `roadmap-crosswalk/fixtures/` (7 deepen negatives) | `roadmap-crosswalk-forbidden-action.schema.json` |
| `AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001` | [temporal-ux/AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md](temporal-ux/AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md) | `temporal-ux/fixtures/` (7 deepen negatives) | `forbidden-action.schema.json` |
| `AS-2.2-TIME-MACHINE-DEEPEN-PREP-001` | [time-machine/AS-2.2-TIME-MACHINE-DEEPEN-PREP-001.md](time-machine/AS-2.2-TIME-MACHINE-DEEPEN-PREP-001.md) | `time-machine/` (see package DEEPEN-FIXTURE-PLAN / fixtures) | `time-machine-forbidden-action.schema.json` |
| `AS-2.2-XPROJ-DEEPEN-PREP-001` | [xproj/AS-2.2-XPROJ-DEEPEN-PREP-001.md](xproj/AS-2.2-XPROJ-DEEPEN-PREP-001.md) | `xproj/fixtures/` (7 deepen negatives) | `xproj-forbidden-action.schema.json` |

**Counted:** 20 deepen cards · 52 deepen negative files · 21 forbidden-action schemas.

Gate credit from these sketches: **NO**. Runner: absent. Production mutation: **NONE**.
