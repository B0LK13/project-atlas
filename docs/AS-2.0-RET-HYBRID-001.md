# AS-2.0-RET-HYBRID-001 — Hybrid retrieval harness

| Field | Value |
|---|---|
| Package | **AS-2.0-RET-HYBRID-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (Wave 2 harness) |
| Class | **RWC** — semantic slot disabled by default |

## Purpose

Deterministic hybrid retrieval **plan** over the certified AS-RET-001 lexical
exact/prefix surface. An optional semantic slot is present in the schema for
forward compatibility but remains **DISABLED by default**. This package does
not invent or ship an embeddings service.

## Surfaces

| Surface | Path |
|---|---|
| Schema | `hybrid-retrieval-plan` |
| Module | `project_atlas.hybrid_retrieval` |
| Doc | `docs/AS-2.0-RET-HYBRID-001.md` |

## Invariants

- Lexical exact / prefix execute via `project_atlas.retrieval.VaultRetriever`
- `semantic_enabled = false` always in emitted plans
- Requesting `enable_semantic=True` fails closed
- No vault writes (plan is in-memory / returned only)
- Bound to `atlas-1.0.0-compat` (AS-2.0-COMPAT-001)
- 1.0 wins conflicts

## Truth boundary

`HYBRID PLAN ≠ EMBEDDINGS SERVICE / ≠ AUTHORITY`

## Non-claims

- Not an embeddings / vector retrieval product
- Not dual ownership of PROV / KCI branches
- Not Atlas 2.0 RELEASE CERTIFIED
- Not authentic estate PILOT
