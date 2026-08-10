# Hybrid Retrieval 2 — Architecture (PREP)

| Field | Value |
|---|---|
| Package | AS-2.2-RET-HYBRID-001 |
| Status | **DESIGN / PREP ONLY** |
| Predecessor | AS-2.0-RET-HYBRID-001 (`hybrid_retrieval_plan` v1) |
| Truth boundary | `HYBRID PLAN ≠ EMBEDDINGS SERVICE / ≠ AUTHORITY` |
| Semantic boundary | `SEMANTIC INDEX ≠ CANONICAL TRUTH` |

## 1. Goal

Specify a **retrieval fusion** pipeline that combines deterministic Atlas
signals before any optional semantic/vector assist:

```text
query
  → normalize (kind, value, mode, filters)
  → slot fan-out (parallel, bounded)
       lexical_exact | lexical_prefix
       metadata
       graph (derived)
       temporal (validity / as-of)
       authority (objective signals only)
       semantic (OPTIONAL, disabled by default)
  → fuse (deterministic rank + explain)
  → results + receipts (derived, regenerable)
```

No slot may write Layer B authority. Semantic hits are always labeled
`derived` and regenerable from a versioned index contract.

## 2. Slot model

| Slot | Substrate today | 2.2 intent | Default |
|---|---|---|---|
| `lexical_exact` | AS-RET-001 / VaultRetriever | Keep; primary | on when mode=exact |
| `lexical_prefix` | AS-RET-001 | Keep; primary | on when mode=prefix |
| `metadata` | frontmatter / indexes | Typed filter (project, type, tag, lifecycle) | idle until filters present |
| `graph` | Graphify / KF2 derived | Neighbor / path expand; **≠ authority** | idle / opt-in |
| `temporal` | AS-CORE-005 / bitemporal | as-of / validity window filter | idle until as-of set |
| `authority` | objective signals (source, verification, freshness) | Re-rank / demote stale or unverified | advisory |
| `semantic` | **absent** (disabled in 2.0 plan) | Optional vector slot behind explicit contract | **disabled** |

### Semantic slot rules (normative for future impl)

1. Derived · regenerable · versioned · non-authoritative.
2. Index identity includes model/provider pin + corpus digest + schema version.
3. Enabling without a registered index contract **fails closed**.
4. Semantic-only results cannot outrank conflicting certified lexical claims
   without an explicit operator policy receipt (post-unlock design).
5. Isolated benchmark / spike permitted under fixtures; never as canonical truth.

## 3. Fusion sketch (deterministic)

Proposed fusion order (PREP — not shipped):

1. Collect per-slot hits with stable IDs.
2. Deduplicate by `(record_type, record_id)`.
3. Apply hard filters: temporal fail → drop or mark `unknown`; never invent.
4. Apply authority demotions (stale / unverified) as **signals**, not delete-by-default.
5. Preserve lexical hits that semantic alone would omit.
6. Emit explainable `fusion_trace` (slot contributions only; no wall-clock).

Byte-stable serialization: `sort_keys=True`, NFR-001 (no `generated.at`).

## 4. Compatibility

| Constraint | Rule |
|---|---|
| 1.0 wins | Conflicts with certified 1.0 Core semantics lose for 2.2 prep |
| AS-2.0 plan v1 | Remain valid; 2.2 draft is a **new** plan kind / schema draft |
| Compat pin | Post-unlock pin to `v2.1.0` via `AS-2.2-COMPAT-PIN-001` |
| Live path freeze | Do not mutate `hybrid_retrieval.py` defaults pre-unlock |

## 5. Interfaces (sketch)

| Interface | Role |
|---|---|
| `HybridRetrieval2Plan` | Docs schema draft under `schemas/` |
| `HybridSlotRunner` | Per-slot adapter (future); lexical reuses VaultRetriever |
| `FusionPolicy` | Deterministic rank + fail-closed flags |
| `SemanticIndexContract` | Versioned; absent ⇒ semantic disabled |
| `BenchmarkHarness` | Case inventory under `benchmarks/` |

## 6. Relationship to Context Compiler

Hybrid Retrieval 2 produces **candidate evidence**. Context Compiler
(AS-2.2-CTX-COMPILER / AS-2.2-RET-CTX) consumes candidates → authority →
freshness → conflict filtering → budget → context pack. This PREP package
does **not** own context-pack production.

## 7. Threat notes (delta)

| ID | Risk | Mitigation (design) |
|---|---|---|
| T-RET2-001 | Semantic elevates LLM similarity to authority | Disabled default; derived label; 1.0 wins |
| T-RET2-002 | Graph rank invents winners | Graph≠authority; no promote |
| T-RET2-003 | Unbounded fan-out / amplification | Slot budgets in benchmark + future NFR |
| T-RET2-004 | Secret leakage via retrieval explain | Metadata-only; redact |

## 8. Implementation gate

Production code under `src/project_atlas/` for Hybrid Retrieval 2 opens only when:

1. `ATLAS_2_1_RELEASE_CERTIFIED = YES` (`v2.1.0`), and
2. `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` fires, and
3. Package entry gate + sole-writer assignment for the live module surface.

Until then: docs / fixtures / benchmarks only.
