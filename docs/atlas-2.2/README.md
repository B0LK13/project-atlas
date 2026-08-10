# Atlas 2.2 — Intelligence prep index (SAFE pre-v2.1.0)

| Field | Value |
|---|---|
| Status | **PREP ONLY** — docs / contracts / fixtures / benchmarks / ADRs |
| Unlock gate | `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (after `v2.1.0`) |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| Tip baseline (index cut) | MAIN `c538235` (= `origin/main` at branch cut) |
| Charter | [CHARTER.md](CHARTER.md) |
| Strategy DAG | [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md) |
| Roadmap crosswalk | [`roadmap-crosswalk/CROSSWALK.md`](roadmap-crosswalk/CROSSWALK.md) |

## Purpose

Index all **landed** Atlas 2.2 knowledge-intelligence PREP packages
(architecture, contract stubs, fixture sketches, ADRs) **without** mutating
2.1 live Core paths (`knowledge_compiler`, `retrieval`, hybrid plan module)
or inventing authentic-estate PILOT credit.

Package directories under this tree are **preserved**; this README is an
integration index only (builds on H01 #173 multi-package restore; extends through
#179–#199 wave-2 merges and #208–#210 wave-1 deepen merges).

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
| **COMPAT-PIN** | `AS-2.2-COMPAT-PIN-PREP-001` | [#196](https://github.com/B0LK13/project-atlas/pull/196) | [compat-pin/](compat-pin/) · [compat-pin/contracts/](compat-pin/contracts/) · [compat-pin/fixtures/](compat-pin/fixtures/) · [compat-pin/AS-2.2-COMPAT-PIN-PREP-001.md](compat-pin/AS-2.2-COMPAT-PIN-PREP-001.md) |
| **ESTATE-OPS** | `AS-2.2-ESTATE-OPS-PREP-001` | [#197](https://github.com/B0LK13/project-atlas/pull/197) | [estate-ops/](estate-ops/) · [estate-ops/contracts/](estate-ops/contracts/) · [estate-ops/fixtures/](estate-ops/fixtures/) · [estate-ops/AS-2.2-ESTATE-OPS-PREP-001.md](estate-ops/AS-2.2-ESTATE-OPS-PREP-001.md) |
| **DOC-CHARTER** | `AS-2.2-DOC-CHARTER-PREP-001` | [#199](https://github.com/B0LK13/project-atlas/pull/199) | [doc-charter/](doc-charter/) · [doc-charter/contracts/](doc-charter/contracts/) · [doc-charter/fixtures/](doc-charter/fixtures/) · [doc-charter/adr/](doc-charter/adr/) · [doc-charter/AS-2.2-DOC-CHARTER-PREP-001.md](doc-charter/AS-2.2-DOC-CHARTER-PREP-001.md) |
| **MEM-DEEPEN** | `AS-2.2-MEM-GOV-DEEPEN-PREP-001` | [#208](https://github.com/B0LK13/project-atlas/pull/208) | [mem-gov/AS-2.2-MEM-GOV-DEEPEN-PREP-001.md](mem-gov/AS-2.2-MEM-GOV-DEEPEN-PREP-001.md) · [mem-gov/INVARIANTS.md](mem-gov/INVARIANTS.md) · [mem-gov/FIXTURE-PLAN.md](mem-gov/FIXTURE-PLAN.md) · [mem-gov/contracts/](mem-gov/contracts/) · [mem-gov/fixtures/](mem-gov/fixtures/) · [mem-gov/adr/ADR-2.2-MEM-GOV-001-governed-agent-memory-deepen-prep.md](mem-gov/adr/ADR-2.2-MEM-GOV-001-governed-agent-memory-deepen-prep.md) |
| **RESEARCH-DEEPEN** | `AS-2.2-RESEARCH-DEEPEN-PREP-001` | [#209](https://github.com/B0LK13/project-atlas/pull/209) | [research/AS-2.2-RESEARCH-DEEPEN-PREP-001.md](research/AS-2.2-RESEARCH-DEEPEN-PREP-001.md) · [research/INVARIANTS.md](research/INVARIANTS.md) · [research/DEEPEN-FIXTURE-PLAN.md](research/DEEPEN-FIXTURE-PLAN.md) · [research/contracts/](research/contracts/) · [research/fixtures/](research/fixtures/) · [research/adr/ADR-2.2-RESEARCH-001-workspace-deepen-prep.md](research/adr/ADR-2.2-RESEARCH-001-workspace-deepen-prep.md) |
| **RET-DEEPEN** | `AS-2.2-RET-HYBRID-DEEPEN-PREP-001` | [#220](https://github.com/B0LK13/project-atlas/pull/220) | [ret-hybrid/](ret-hybrid/) · [ret-hybrid/AS-2.2-RET-HYBRID-DEEPEN-PREP-001.md](ret-hybrid/AS-2.2-RET-HYBRID-DEEPEN-PREP-001.md) |
| **CTX-DEEPEN** | `AS-2.2-CTX-DEEPEN-PREP-001` | [#215](https://github.com/B0LK13/project-atlas/pull/215) | [ctx-compiler/AS-2.2-CTX-DEEPEN-PREP-001.md](ctx-compiler/AS-2.2-CTX-DEEPEN-PREP-001.md) |
| **REALITY-LIVE-DEEPEN** | `AS-2.2-REALITY-LIVE-DEEPEN-PREP-001` | [#217](https://github.com/B0LK13/project-atlas/pull/217)/[#219](https://github.com/B0LK13/project-atlas/pull/219) | [reality-live/AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md](reality-live/AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md) |
| **TIME-DEEPEN** | `AS-2.2-TIME-MACHINE-DEEPEN-PREP-001` | [#218](https://github.com/B0LK13/project-atlas/pull/218) | [time-machine/AS-2.2-TIME-MACHINE-DEEPEN-PREP-001.md](time-machine/AS-2.2-TIME-MACHINE-DEEPEN-PREP-001.md) |
| **DOD-DEEPEN** | `AS-2.2-DOD-DEEPEN-PREP-001` | [#210](https://github.com/B0LK13/project-atlas/pull/210) | [dod-compiler/AS-2.2-DOD-DEEPEN-PREP-001.md](dod-compiler/AS-2.2-DOD-DEEPEN-PREP-001.md) · [dod-compiler/INVARIANTS.md](dod-compiler/INVARIANTS.md) · [dod-compiler/FIXTURE-PLAN.md](dod-compiler/FIXTURE-PLAN.md) · [dod-compiler/contracts/](dod-compiler/contracts/) · [dod-compiler/fixtures/](dod-compiler/fixtures/) · [dod-compiler/adr/ADR-2.2-DOD-002-dod-compiler-deepen-prep.md](dod-compiler/adr/ADR-2.2-DOD-002-dod-compiler-deepen-prep.md) |
| **PREP-STATUS** | `AS-2.2-PREP-STATUS-001` | [#203](https://github.com/B0LK13/project-atlas/pull/203) | [PREP-STATUS.md](PREP-STATUS.md) |
| **CROSSWALK** | `AS-2.2-ROADMAP-CROSSWALK-PREP-001` | [#206](https://github.com/B0LK13/project-atlas/pull/206) | [roadmap-crosswalk/](roadmap-crosswalk/) · [CROSSWALK.md](roadmap-crosswalk/CROSSWALK.md) |

Shared stubs: [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md) · [FIXTURE-PLAN.md](FIXTURE-PLAN.md) · [fixtures/README.md](fixtures/README.md) · [adr/](adr/) · [roadmap-crosswalk/](roadmap-crosswalk/)

## Explicit non-claims

- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not `ATLAS_2_1_RELEASE_CERTIFIED=YES`
- Not production mutation of `project_atlas.retrieval` / `knowledge_compiler`
- Not an embeddings / vector retrieval product as Layer B authority
- Not authentic estate PILOT / not `v2.1.0` / not `v2.2.0` certification
- Fixture PASS ≠ authentic PILOT PASS

## Harvest note

Parallel PREP merges (#159–#172, then #179–#199, then #208–#210 deepen) left
package directories intact but `README.md` was last-writer-wins (#159). This
index restores the multi-package tree through tip (`d7c4d79`) without reopening
runtime surfaces.
