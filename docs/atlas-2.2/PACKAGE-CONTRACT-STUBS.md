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


## Forbidden-action stubs — deepen wave (AS-2.2-PREP-FIXTURE-ROLLUP-001)

Planning traceability only — not shipped package data / not CI gate credit.
Cut tip: `8c48bb3` / TREE `da63619`. Unlock NO. `ATLAS_2_1_RELEASE_CERTIFIED=NO`.

| Schema (package path) | Owning deepen package |
|---|---|
| [`ask-atlas-2/contracts/ask2-forbidden-action.schema.json`](ask-atlas-2/contracts/ask2-forbidden-action.schema.json) | `AS-2.2-ASK2-DEEPEN-PREP-001` |
| [`chatgpt-live/contracts/chatgpt-live-deepen-forbidden-action.schema.json`](chatgpt-live/contracts/chatgpt-live-deepen-forbidden-action.schema.json) | `AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001` |
| [`chatgpt-live/contracts/forbidden-action.schema.json`](chatgpt-live/contracts/forbidden-action.schema.json) | `AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001` |
| [`compat-pin/contracts/compat-pin-forbidden-action.schema.json`](compat-pin/contracts/compat-pin-forbidden-action.schema.json) | `AS-2.2-COMPAT-PIN-DEEPEN-PREP-001` |
| [`conflict-ux/contracts/conflict-ux-forbidden-action.schema.json`](conflict-ux/contracts/conflict-ux-forbidden-action.schema.json) | `AS-2.2-CONFLICT-UX-DEEPEN-PREP-001` |
| [`ctx-compiler/contracts/ctx-forbidden-action.schema.json`](ctx-compiler/contracts/ctx-forbidden-action.schema.json) | `AS-2.2-CTX-DEEPEN-PREP-001` |
| [`doc-charter/contracts/doc-charter-forbidden-action.schema.json`](doc-charter/contracts/doc-charter-forbidden-action.schema.json) | `AS-2.2-DOC-CHARTER-DEEPEN-PREP-001` |
| [`dod-compiler/contracts/dod-forbidden-action.schema.json`](dod-compiler/contracts/dod-forbidden-action.schema.json) | `AS-2.2-DOD-DEEPEN-PREP-001` |
| [`estate-ops/contracts/estate-ops-forbidden-action.schema.json`](estate-ops/contracts/estate-ops-forbidden-action.schema.json) | `AS-2.2-ESTATE-OPS-DEEPEN-PREP-001` |
| [`intel-slice/contracts/intel-slice-forbidden-action.schema.json`](intel-slice/contracts/intel-slice-forbidden-action.schema.json) | `AS-2.2-INTEL-SLICE-DEEPEN-PREP-001` |
| [`kci-engine/contracts/kci-forbidden-action.schema.json`](kci-engine/contracts/kci-forbidden-action.schema.json) | `AS-2.2-KCI-ENGINE-DEEPEN-PREP-001` |
| [`kf2-fabric/contracts/kf2-fabric-forbidden-action.schema.json`](kf2-fabric/contracts/kf2-fabric-forbidden-action.schema.json) | `AS-2.2-KF2-FABRIC-DEEPEN-PREP-001` |
| [`mem-gov/contracts/mem-gov-forbidden-action.schema.json`](mem-gov/contracts/mem-gov-forbidden-action.schema.json) | `AS-2.2-MEM-GOV-DEEPEN-PREP-001` |
| [`reality-gap/contracts/reality-gap-forbidden-action.schema.json`](reality-gap/contracts/reality-gap-forbidden-action.schema.json) | `AS-2.2-REALITY-GAP-DEEPEN-PREP-001` |
| [`reality-live/contracts/reality-live-forbidden-action.schema.json`](reality-live/contracts/reality-live-forbidden-action.schema.json) | `AS-2.2-REALITY-LIVE-DEEPEN-PREP-001` |
| [`research/contracts/research-forbidden-action.schema.json`](research/contracts/research-forbidden-action.schema.json) | `AS-2.2-RESEARCH-DEEPEN-PREP-001` |
| [`ret-hybrid/contracts/ret-hybrid-forbidden-action.schema.json`](ret-hybrid/contracts/ret-hybrid-forbidden-action.schema.json) | `AS-2.2-RET-HYBRID-DEEPEN-PREP-001` |
| [`roadmap-crosswalk/contracts/roadmap-crosswalk-forbidden-action.schema.json`](roadmap-crosswalk/contracts/roadmap-crosswalk-forbidden-action.schema.json) | `AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001` |
| [`temporal-ux/contracts/forbidden-action.schema.json`](temporal-ux/contracts/forbidden-action.schema.json) | `AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001` |
| [`time-machine/contracts/time-machine-forbidden-action.schema.json`](time-machine/contracts/time-machine-forbidden-action.schema.json) | `AS-2.2-TIME-MACHINE-DEEPEN-PREP-001` |
| [`xproj/contracts/xproj-forbidden-action.schema.json`](xproj/contracts/xproj-forbidden-action.schema.json) | `AS-2.2-XPROJ-DEEPEN-PREP-001` |

**FORBIDDEN:** promoting these stubs into `src/project_atlas/schemas/` before unlock;
using fixture PASS as release cert or authentic PILOT credit.
