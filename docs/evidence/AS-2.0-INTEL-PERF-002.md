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
