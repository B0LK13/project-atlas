# Atlas 2.2 — Intelligence prep (SAFE pre-v2.1.0)

| Field | Value |
|---|---|
| Status | **PREP ONLY** — docs / contracts / fixtures / benchmarks |
| Unlock | `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0` |
| Tip baseline (prep open) | MAIN `a1e0972` / TREE `c6cfe95` (= `origin/main` at branch cut) |
| Directive context | `D-PROJECT-ATLAS-FORCED-MULTIAGENT-ORCHESTRATION-001` · evidence under `atlas-2.1-productionization-001` |

## Purpose

Hold **safe pre-v2.1.0** architecture, contract stubs, fixture sketches, and
benchmark harness designs for Atlas 2.2 knowledge-intelligence packages
**without** mutating 2.1 live Core paths (`knowledge_compiler`, `retrieval`,
or the AS-2.0-RET-HYBRID live plan module).

## Tree

| Path | Role |
|---|---|
| [CHARTER.md](CHARTER.md) | Prep firewall + truth boundaries |
| [AS-2.2-RET-HYBRID-001.md](AS-2.2-RET-HYBRID-001.md) | Hybrid Retrieval 2 package contract (PREP) |
| [HYBRID-RETRIEVAL-2.md](HYBRID-RETRIEVAL-2.md) | Architecture: lexical · metadata · graph · temporal · authority · optional semantic |
| [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md) | FR / NFR stubs for RET2 family |
| [FIXTURE-PLAN.md](FIXTURE-PLAN.md) | Fixture family inventory |
| [fixtures/](fixtures/) | Docs-only sample payloads (non-CI) |
| [benchmarks/](benchmarks/) | Benchmark case sketches (non-SLO) |
| [schemas/](schemas/) | Draft JSON Schema stubs (docs-only; not package data) |

## Roadmap link

Executable DAG: [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md).  
Gap row: `GAP-NS-002` → production path package `AS-2.2-RET-CTX-001` (post-unlock).  
This PREP package (`AS-2.2-RET-HYBRID-001`) owns architecture + fixtures + benchmarks only.

## Explicit non-claims

- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not production mutation of `project_atlas.retrieval` / `knowledge_compiler`
- Not an embeddings / vector retrieval product
- Not authentic estate PILOT / not `v2.1.0` / not `v2.2.0` certification
