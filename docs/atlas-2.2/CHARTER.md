# Atlas 2.2 — Prep charter (SAFE pre-v2.1.0)

## Allowed now

- Architecture / ADR sketches under `docs/atlas-2.2/`
- Contract stubs and **docs-only** schema drafts
- Fixture sketches and sample JSON under `docs/atlas-2.2/fixtures/`
- Benchmark harness designs and case inventories under `docs/atlas-2.2/benchmarks/`
- Strategy cross-links that do **not** widen 2.1 release scope

## Forbidden until unlock

- Dependency-bearing production mutations of:
  - `src/project_atlas/knowledge_compiler.py`
  - `src/project_atlas/retrieval.py`
  - `src/project_atlas/hybrid_retrieval.py` live semantics / schema version bumps that change 2.1 defaults
- Shipping embeddings as canonical Layer B authority
- Relabeling AS-2.0-RET-HYBRID plan harness as 2.2 intelligence certification
- Fixture waiver for authentic PILOT

## Truth boundaries (carry forward)

| Boundary | Meaning |
|---|---|
| `HYBRID PLAN ≠ EMBEDDINGS SERVICE / ≠ AUTHORITY` | AS-2.0-RET-HYBRID-001 |
| `SEMANTIC INDEX ≠ CANONICAL TRUTH` | Vectors derived, regenerable, versioned, non-authoritative |
| `UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy` | ADR / 2.1 charter |
| `LLM ≠ authority` | Quarantine-first; provenance required |

## Relationship to 2.0 / 2.1

| Line | Role |
|---|---|
| AS-RET-001 | Certified lexical exact/prefix retrieval (1.0) |
| AS-2.0-RET-HYBRID-001 | Deterministic hybrid **plan** harness; semantic slot disabled |
| AS-2.1 live surfaces | API / MCP / web / sched / L3 — do not regress for 2.2 prep |
| AS-2.2-RET-HYBRID-001 (this) | Architecture + fixtures + benchmarks for Hybrid Retrieval 2 |
| AS-2.2-RET-CTX-001 | Post-`v2.1.0` production path (hybrid + context packs) |

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO` until `v2.1.0` cert.
