# Atlas 2.2 — Intelligence prep tree (SAFE pre-v2.1.0)

| Field | Value |
|---|---|
| Status | **PREP ONLY** — docs / contracts / fixtures / benchmarks / ADRs |
| Unlock | `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0` |
| Production mutation | **FORBIDDEN** on 2.1 tip |
| Charter | [CHARTER.md](CHARTER.md) |
| Strategy DAG | [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md) |

## Purpose

Hold **safe pre-v2.1.0** architecture, contract stubs, fixture sketches, and
benchmark harness designs for Atlas 2.2 knowledge-intelligence packages
**without** mutating 2.1 live Core paths (`knowledge_compiler`, `retrieval`,
or the AS-2.0-RET-HYBRID live plan module).

## Packages seeded (COMPLEMENTARY lanes)

| Package | Path | Notes |
|---|---|---|
| AS-2.2-RET-HYBRID-001 | [`AS-2.2-RET-HYBRID-001.md`](AS-2.2-RET-HYBRID-001.md), [`HYBRID-RETRIEVAL-2.md`](HYBRID-RETRIEVAL-2.md), [`benchmarks/`](benchmarks/), [`fixtures/hybrid-retrieval/`](fixtures/hybrid-retrieval/), [`schemas/`](schemas/) | Hybrid Retrieval 2 prep · PR #159 |
| AS-2.2-KCI-ENGINE-PREP-001 | [`kci-engine/`](kci-engine/), [`AS-2.2-KCI-ENGINE-PREP-001.md`](AS-2.2-KCI-ENGINE-PREP-001.md) | Knowledge CI engine · PR #160 |
| AS-2.2-CTX-COMPILER-001 | [`ctx-compiler/`](ctx-compiler/), [`contracts/ctx-compiler/`](contracts/ctx-compiler/), [`fixtures/ctx-compiler/`](fixtures/ctx-compiler/), [`adr/ADR-2.2-001-context-compiler-pipeline.md`](adr/ADR-2.2-001-context-compiler-pipeline.md) | Context Compiler · PR #161 |
| AS-2.2-REALITY-LIVE-001 | [`reality-live/`](reality-live/), [`contracts/reality-live/`](contracts/reality-live/) | Collectors / planes · PR #167 |
| AS-2.2-TIME-MACHINE-001 | [`time-machine/`](time-machine/), [`AS-2.2-TIME-MACHINE-001.md`](AS-2.2-TIME-MACHINE-001.md) | As-of + T1/T2 diff · PR #168 |
| AS-2.2-MEM-GOV-001 | [`mem-gov/`](mem-gov/), [`contracts/mem-gov/`](contracts/mem-gov/), [`fixtures/mem-gov/`](fixtures/mem-gov/), [`adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md`](adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md) | Governed agent memory · PR #169 |
| AS-2.2-DOD-COMPILER-001 | [`dod-compiler/`](dod-compiler/), [`contracts/dod-compiler/`](contracts/dod-compiler/), [`fixtures/dod-compiler/`](fixtures/dod-compiler/), [`AS-2.2-DOD-COMPILER-001.md`](AS-2.2-DOD-COMPILER-001.md) | Goal→DoD→proof · PR #170 |
| AS-2.2-RESEARCH-001 | [`research/`](research/), [`contracts/research/`](contracts/research/), [`fixtures/research/`](fixtures/research/) | Research workspace + Ask Atlas 2 · PR #171 |
| AS-2.2-REALITY-GAP-PREP-001 | [`reality-gap/`](reality-gap/) | Reality gap contracts/fixtures · PR #172 |

Shared stubs: [`PACKAGE-CONTRACT-STUBS.md`](PACKAGE-CONTRACT-STUBS.md) · [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) · [`fixtures/README.md`](fixtures/README.md)

## Explicit non-claims

- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not production mutation of `project_atlas.retrieval` / `knowledge_compiler`
- Not an embeddings / vector retrieval product
- Not authentic estate PILOT / not `v2.1.0` / not `v2.2.0` certification
- Fixture PASS ≠ authentic PILOT PASS

## Harvest note

Parallel PREP merges left package directories intact (COMPLEMENTARY) but
`README.md` was last-writer-wins (#159). This index restores the multi-package
tree without reopening runtime surfaces.
