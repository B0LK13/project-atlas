# AS-2.0-INTEL-PERF-003 — Compact candidate materialization

Reduce dense-group materialization cost without dropping pairs or
changing contradiction classification / candidate ids.

## Changes

- `ContradictionCandidate` is a frozen slots record with pydantic-compatible
  `model_dump` / `model_dump_json`
- Precomputed claim metadata (windows, authority, evidence keys, lineage)
- Interned uncertainty / authority-relation / generated metadata
- Fast 1+1 evidence merge
- Skip `windows_relation` when either start bound is missing

## Measured (this checkout)

| N | groups | materialize | wall | pairs |
|---|---|---|---|---|
| 1k | 200 | yes | 0.019s | 1600 |
| 10k | 50 dense | yes | 3.793s | 666650 |
| 10k | 2000 | yes | 1.170s | 16000 |
| 100k | 20000 | no | 2.202s | 160000 counted |

Wave-8 dense 10k was ~8.8s. This package is ~2.3× faster.

## Residual

Still **MAJOR** for pathological density: 666650 qualifying candidates
must be allocated and hashed. That cost is the semantic floor. No pair
is dropped.

`DERIVED_INTELLIGENCE_IS_AUTHORITY = NO`
`CONTRADICTION_IS_PROVEN_FALSEHOOD = NO`
