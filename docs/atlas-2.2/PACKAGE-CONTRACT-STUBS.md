# Atlas 2.2 — Package contract stubs (RET family)

Status: **PREP ONLY**. Stubs are planning traceability — not certified FRs.

## Package map

| Stub ID | Theme | Prep status | Post-unlock |
|---|---|---|---|
| **AS-2.2-RET-HYBRID-001** | Hybrid Retrieval 2 architecture + fixtures + benchmarks | **ACTIVE PREP** | feeds RET-CTX |
| AS-2.2-RET-SEMIDX-001 | Semantic index contract (derived, versioned) | reserved | after RET-HYBRID arch |
| AS-2.2-RET-CTX-001 | Hybrid + context pack production path | roadmap READY post-unlock | production |
| AS-RET2-HYBRID-001 | Alias note — prefer `AS-2.2-RET-HYBRID-001` | superseded naming | — |

## FR stubs — AS-2.2-RET-HYBRID-001

| FR ID | Requirement (stub) | Depends on |
|---|---|---|
| FR-2.2-RET-001 | Fusion plan declares slots: lexical, metadata, graph, temporal, authority, optional semantic | AS-RET-001 |
| FR-2.2-RET-002 | Semantic slot disabled by default; enable fails closed without index contract | AS-2.0-RET-HYBRID-001 |
| FR-2.2-RET-003 | Graph slot consumes derived projections only; never elevates to Layer B | Graph≠authority |
| FR-2.2-RET-004 | Temporal filters fail closed to unknown when validity cannot be resolved | AS-CORE-005 |
| FR-2.2-RET-005 | Fusion is deterministic and regenerable (no wall-clock in plan) | NFR-001 |
| FR-2.2-RET-006 | Benchmark harness evaluates lexical + fail-closed semantic cases on fixtures | this PREP |

## NFR stubs

| NFR ID | Requirement (stub) |
|---|---|
| NFR-2.2-RET-001 | Prep must not mutate `knowledge_compiler` / `retrieval` live defaults before unlock |
| NFR-2.2-RET-002 | Slot fan-out budgets prevent unbounded result amplification |
| NFR-2.2-RET-003 | Secrets findings remain metadata-only in explain/trace |
| NFR-2.2-RET-004 | Docs schema drafts are not shipped as `importlib.resources` package data until authorized |

## Boundary (IN / OUT / FORBIDDEN)

- **IN:** architecture, docs schema draft, fixture samples, benchmark cases, strategy links.
- **OUT:** future live HybridRetrieval2 planner module; SemanticIndexContract registry.
- **FORBIDDEN:** embeddings as authority; silent promote; dual-own of CTX/KCI/PROV; CI gate credit from sketches alone.
