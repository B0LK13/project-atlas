# Hybrid Retrieval 2 — Benchmark harness sketches

Status: **PREP ONLY**. Not production SLOs. Not CI gate credit.

Aligns with north-star §97 performance benchmark design and AS-2.0
`PERFORMANCE-BUDGETS.md` preference for **deterministic** signals
(file/byte/op counts) over wall-clock hard fails.

## Purpose

Reserve benchmark case IDs and expected invariant classes for Hybrid
Retrieval 2 so a post-`v2.1.0` harness can land without redesigning the
evaluation surface.

## Case inventory

| Case ID | File | Invariant class |
|---|---|---|
| BM-RET2-001 | `cases/BM-RET2-001-lexical-exact.json` | Lexical exact hit stable |
| BM-RET2-002 | `cases/BM-RET2-002-lexical-prefix.json` | Lexical prefix hit stable |
| BM-RET2-003 | `cases/BM-RET2-003-semantic-fail-closed.json` | Semantic enable fails closed |
| BM-RET2-004 | `cases/BM-RET2-004-fusion-preserve-lexical.json` | Fusion preserves lexical vs semantic |

## Soft budgets (design intent)

| Signal | Soft budget | Hard fail in PREP? |
|---|---|---|
| Fixture vault file count | bounded by case inventory | no |
| Plan JSON byte digest | comparable across runs | yes (when runner exists) |
| Slot fan-out ops | countable | advisory |
| Wall-clock latency | deferred | **no** in CI prep |

## Runner (future)

Proposed (not shipped): `atlas ret-hybrid-bench --cases docs/atlas-2.2/benchmarks/cases`
— fails closed if any case mutates vault fingerprint; emits receipt under
`generated/ops/` only after unlock + entry gate.

## Non-claims

- Not a performance certification
- Not embeddings quality eval
- Not RELEASE / PILOT evidence
