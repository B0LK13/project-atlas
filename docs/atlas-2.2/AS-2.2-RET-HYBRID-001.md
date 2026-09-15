# AS-2.2-RET-HYBRID-001 — Hybrid Retrieval 2 (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-RET-HYBRID-001** |
| Class | **DOCUMENTATION_ONLY / FIXTURE_SKETCH / BENCHMARK_SKETCH** |
| Status | **PREP** (SAFE pre-`v2.1.0`) |
| Gap | `GAP-NS-002` (feeds post-unlock `AS-2.2-RET-CTX-001`) |
| Baseline | MAIN `a1e0972` / TREE `c6cfe95` |
| Sole-writer surface | `docs/atlas-2.2/**` (this package) + strategy cross-links |
| Excluded surface | `src/project_atlas/{knowledge_compiler,retrieval,hybrid_retrieval}.py` live path |

## Problem

Estate-scale retrieval must fuse **lexical**, **metadata**, **graph**,
**temporal**, and **authority** signals — with an **optional** semantic/vector
slot that stays derived and non-authoritative. Today AS-2.0-RET-HYBRID-001
emits a deterministic plan over AS-RET-001 lexical exact/prefix only;
semantic remains disabled.

## User value

Operators and agents get a governed retrieval fusion design that can be
benchmarked and fixture-tested **before** any 2.2 production wiring, without
destabilizing the 2.1 tip.

## Scope (PREP)

| In | Out |
|---|---|
| Architecture (`HYBRID-RETRIEVAL-2.md`) | Live plan module changes |
| FR/NFR stubs | Embeddings service / provider SDK |
| Docs-only schema draft | `src/project_atlas/schemas/` package-data bump |
| Fixture sketches | CI gate credit / RELEASE cert |
| Benchmark case inventory | Production SLO enforcement |

## Owned surface

```text
docs/atlas-2.2/AS-2.2-RET-HYBRID-001.md
docs/atlas-2.2/HYBRID-RETRIEVAL-2.md
docs/atlas-2.2/PACKAGE-CONTRACT-STUBS.md
docs/atlas-2.2/FIXTURE-PLAN.md
docs/atlas-2.2/fixtures/hybrid-retrieval/**
docs/atlas-2.2/benchmarks/**
docs/atlas-2.2/schemas/hybrid-retrieval-2-plan.schema.draft.json
```

## Excluded surface

- `project_atlas.retrieval.VaultRetriever` behavior
- `project_atlas.knowledge_compiler` authority / claim compile
- `project_atlas.hybrid_retrieval` schema_version / package_id / defaults
- AS-2.0-CTX-001 / context_pack production semantics (sibling lane)

## Dependencies

| Depends on | Why |
|---|---|
| AS-RET-001 | Lexical exact/prefix substrate |
| AS-2.0-RET-HYBRID-001 | Existing plan harness + truth boundary |
| AS-2.0-COMPAT-001 / 1.0 wins | Conflict rule |
| AS-CORE-005 / bitemporal (optional slot) | Temporal filter sketch |
| Graph derived projections | Graph slot ≠ authority |

## Downstream (post-unlock)

- `AS-2.2-RET-CTX-001` — hybrid + context pack production path
- `AS-2.2-INTEL-SLICE-001` — intelligence slice consumer
- Ask Atlas 2 query planner (future)

## Fail-closed (design intent)

1. Semantic/vector slot **off by default**; enabling without a versioned index contract fails closed.
2. Graph / KF ranks never promote Layer B authority.
3. Temporal filters that cannot resolve validity windows return **unknown**, not invent.
4. Fusion never silently drops higher-authority lexical hits for semantic similarity.
5. No vault writes from retrieval planning.

## Security properties

- Secrets: metadata-only findings; never log matched content (NFR-004).
- Path safety: fixtures use synthetic relative vault paths only.
- Provider embeddings (if ever wired): quarantine + provenance; LLM ≠ authority.

## Evidence requirements (PREP exit)

- [x] Architecture doc landed
- [x] Fixture family reserved + sample payloads under `docs/atlas-2.2/fixtures/`
- [x] Benchmark case sketches under `docs/atlas-2.2/benchmarks/`
- [x] Docs-only schema draft (not installed as package data)
- [ ] Post-`v2.1.0`: production package opens under unlock event

## Non-claims

- Not Hybrid Retrieval 2 LIVE_PRODUCTION
- Not semantic index spike certified
- Not dual-own of KCI / CTX / PROV production branches
- Not `ATLAS_2_1_RELEASE_CERTIFIED` / not `v2.2.0`
