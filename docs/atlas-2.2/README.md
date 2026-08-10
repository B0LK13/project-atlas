# Atlas 2.2 — Intelligence prep index (SAFE pre-v2.1.0)

| Field | Value |
|---|---|
| Status | **PREP ONLY** — docs / contracts / fixtures / benchmarks / ADRs |
| Unlock gate | `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (after `v2.1.0`) |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| Tip baseline (index cut) | MAIN `1d81a98` (= `origin/main` at branch cut) |
| Charter | [CHARTER.md](CHARTER.md) |
| Strategy DAG | [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md) |

## Purpose

Index all **landed** Atlas 2.2 knowledge-intelligence PREP packages
(architecture, contract stubs, fixture sketches, ADRs) **without** mutating
2.1 live Core paths (`knowledge_compiler`, `retrieval`, hybrid plan module)
or inventing authentic-estate PILOT credit.

Package directories under this tree are **preserved**; this README is an
integration index only (builds on H01 #173 multi-package restore; extends through
#179–#192 tip merges).

## Landed PREP packages

| Short | Package | PR | Entry |
|---|---|---|---|
| **RET** | `AS-2.2-RET-HYBRID-001` | [#159](https://github.com/B0LK13/project-atlas/pull/159) | [AS-2.2-RET-HYBRID-001.md](AS-2.2-RET-HYBRID-001.md) · [HYBRID-RETRIEVAL-2.md](HYBRID-RETRIEVAL-2.md) · [benchmarks/](benchmarks/) · [fixtures/hybrid-retrieval/](fixtures/hybrid-retrieval/) · [schemas/](schemas/) |
| **CTX** | `AS-2.2-CTX-COMPILER-001` | [#161](https://github.com/B0LK13/project-atlas/pull/161) | [ctx-compiler/](ctx-compiler/) · [contracts/ctx-compiler/](contracts/ctx-compiler/) · [fixtures/ctx-compiler/](fixtures/ctx-compiler/) · [adr/ADR-2.2-001-context-compiler-pipeline.md](adr/ADR-2.2-001-context-compiler-pipeline.md) |
| **MEM** | `AS-2.2-MEM-GOV-001` | [#169](https://github.com/B0LK13/project-atlas/pull/169) | [mem-gov/](mem-gov/) · [contracts/mem-gov/](contracts/mem-gov/) · [fixtures/mem-gov/](fixtures/mem-gov/) · [adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md](adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md) · [`docs/AS-2.2-MEM-GOV-001.md`](../AS-2.2-MEM-GOV-001.md) |
| **KCI** | `AS-2.2-KCI-ENGINE-PREP-001` | [#160](https://github.com/B0LK13/project-atlas/pull/160) | [kci-engine/](kci-engine/) · [AS-2.2-KCI-ENGINE-PREP-001.md](AS-2.2-KCI-ENGINE-PREP-001.md) |
| **DoD** | `AS-2.2-DOD-COMPILER-001` | [#170](https://github.com/B0LK13/project-atlas/pull/170) | [dod-compiler/](dod-compiler/) · [contracts/dod-compiler/](contracts/dod-compiler/) · [fixtures/dod-compiler/](fixtures/dod-compiler/) · [AS-2.2-DOD-COMPILER-001.md](AS-2.2-DOD-COMPILER-001.md) |
| **TIME** | `AS-2.2-TIME-MACHINE-001` | [#168](https://github.com/B0LK13/project-atlas/pull/168) | [time-machine/](time-machine/) · [AS-2.2-TIME-MACHINE-001.md](AS-2.2-TIME-MACHINE-001.md) |
| **REALITY-LIVE** | `AS-2.2-REALITY-LIVE-001` | [#167](https://github.com/B0LK13/project-atlas/pull/167) | [reality-live/](reality-live/) · [contracts/reality-live/](contracts/reality-live/) · [`docs/AS-2.2-REALITY-LIVE-001.md`](../AS-2.2-REALITY-LIVE-001.md) |
| **REALITY-GAP** | `AS-2.2-REALITY-GAP-PREP-001` | [#172](https://github.com/B0LK13/project-atlas/pull/172) | [reality-gap/](reality-gap/) |
| **RESEARCH** | `AS-2.2-RESEARCH-001` | [#171](https://github.com/B0LK13/project-atlas/pull/171) | [research/](research/) · [contracts/research/](contracts/research/) · [fixtures/research/](fixtures/research/) · [`docs/AS-2.2-RESEARCH-001.md`](../AS-2.2-RESEARCH-001.md) |
| **CONFLICT** | `AS-2.2-CONFLICT-UX-PREP-001` | [#181](https://github.com/B0LK13/project-atlas/pull/181) | [conflict-ux/](conflict-ux/) · [conflict-ux/contracts/](conflict-ux/contracts/) · [conflict-ux/fixtures/](conflict-ux/fixtures/) · [conflict-ux/AS-2.2-CONFLICT-UX-PREP-001.md](conflict-ux/AS-2.2-CONFLICT-UX-PREP-001.md) |
| **XPROJ** | `AS-2.2-XPROJ-CONTRACT-PREP-001` | [#179](https://github.com/B0LK13/project-atlas/pull/179) | [xproj/](xproj/) · [xproj/contracts/](xproj/contracts/) · [xproj/fixtures/](xproj/fixtures/) · [xproj/AS-2.2-XPROJ-CONTRACT-PREP-001.md](xproj/AS-2.2-XPROJ-CONTRACT-PREP-001.md) |
| **KF2** | `AS-2.2-KF2-FABRIC-PREP-001` | [#186](https://github.com/B0LK13/project-atlas/pull/186) | [kf2-fabric/](kf2-fabric/) · [kf2-fabric/contracts/](kf2-fabric/contracts/) · [kf2-fabric/fixtures/](kf2-fabric/fixtures/) · [kf2-fabric/AS-2.2-KF2-FABRIC-PREP-001.md](kf2-fabric/AS-2.2-KF2-FABRIC-PREP-001.md) |
| **ASK2** | `AS-2.2-ASK2-DEEPEN-PREP-001` | [#188](https://github.com/B0LK13/project-atlas/pull/188) | [ask-atlas-2/](ask-atlas-2/) · [ask-atlas-2/contracts/](ask-atlas-2/contracts/) · [ask-atlas-2/fixtures/](ask-atlas-2/fixtures/) · [ask-atlas-2/AS-2.2-ASK2-DEEPEN-PREP-001.md](ask-atlas-2/AS-2.2-ASK2-DEEPEN-PREP-001.md) |
| **INTEL** | `AS-2.2-INTEL-SLICE-PREP-001` | [#189](https://github.com/B0LK13/project-atlas/pull/189) | [intel-slice/](intel-slice/) · [intel-slice/fixtures/](intel-slice/fixtures/) · [intel-slice/AS-2.2-INTEL-SLICE-PREP-001.md](intel-slice/AS-2.2-INTEL-SLICE-PREP-001.md) |
| **CHATGPT** | `AS-2.2-CHATGPT-LIVE-PREP-001` | [#191](https://github.com/B0LK13/project-atlas/pull/191) | [chatgpt-live/](chatgpt-live/) · [chatgpt-live/contracts/](chatgpt-live/contracts/) · [chatgpt-live/fixtures/](chatgpt-live/fixtures/) · [chatgpt-live/AS-2.2-CHATGPT-LIVE-PREP-001.md](chatgpt-live/AS-2.2-CHATGPT-LIVE-PREP-001.md) |
| **TEMPORAL** | `AS-2.2-TEMPORAL-UX-PREP-001` | [#192](https://github.com/B0LK13/project-atlas/pull/192) | [temporal-ux/](temporal-ux/) · [temporal-ux/contracts/](temporal-ux/contracts/) · [temporal-ux/fixtures/](temporal-ux/fixtures/) · [temporal-ux/AS-2.2-TEMPORAL-UX-PREP-001.md](temporal-ux/AS-2.2-TEMPORAL-UX-PREP-001.md) |

Shared stubs: [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md) · [FIXTURE-PLAN.md](FIXTURE-PLAN.md) · [fixtures/README.md](fixtures/README.md) · [adr/](adr/)

## Explicit non-claims

- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not `ATLAS_2_1_RELEASE_CERTIFIED=YES`
- Not production mutation of `project_atlas.retrieval` / `knowledge_compiler`
- Not an embeddings / vector retrieval product as Layer B authority
- Not authentic estate PILOT / not `v2.1.0` / not `v2.2.0` certification
- Fixture PASS ≠ authentic PILOT PASS

## Harvest note

Parallel PREP merges (#159–#172, then #179–#192) left package directories
intact but `README.md` was last-writer-wins (#159). This index restores the
multi-package tree through tip (#192) without reopening runtime surfaces.
