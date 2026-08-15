# AS-2.0-INTEL-PERF-002 — Candidate-build optimization

MAJOR residual after PERF-001: dense same-slot groups still materialize
every qualifying candidate. This package speeds construction without
dropping pairs or changing candidate ids.

## Changes

- Merge already-sorted evidence tuples
- Intern review strings and generated metadata
- `hashlib.sha256(..., usedforsecurity=False)` (same digest)
- `materialize=False` count-only report for large-N measurement

## Truth boundary

Never drop a qualifying pair to save time.
`DERIVED_INTELLIGENCE_IS_AUTHORITY = NO`

## Measured (this checkout)

| N | groups | materialize | wall | pairs | candidates |
|---|---|---|---|---|---|
| 1k | 200 | yes | 0.023s | 1600 | 1600 |
| 10k | 50 dense | yes | 8.761s | 666650 | 666650 |
| 10k | 2000 | yes | 1.202s | 16000 | 16000 |
| 100k | 20000 | no | 1.896s | 160000 | 160000 counted |

Dense 10k remains **MAJOR**: qualifying candidates must still be
materialized. Count-only mode is for measurement, not a semantic skip.
