# Evidence — AS-MVP-001-FRESHNESS-TRUTH-001

Package: `AS-MVP-001-FRESHNESS-TRUTH-001`
Date: 2026-08-23
Base: `4e71cce0d1c97f408347e256300a41590da4c352`

## Purpose

Portfolio stale-knowledge and H-006 must not:

1. Treat Unix-epoch / pre-1980 `modified_at` as fifty years of real age.
2. Demand quarantined sources appear individually in `stale-knowledge.json`
   (AS-SEC-001).

## Changes

- `portfolio.stale_knowledge` classifies untrusted mtimes as `unknown`, not stale.
- H-006 emits `H-006-untrusted` (warning) for epoch metadata and skips
  silent/launder cross-check for those sources.
- H-006 skips quarantined source ids in the portfolio citation cross-check.
- Pilot scenario tests pin copied mtimes so checkout epoch cannot age nebula.

## Honesty

- This does not invent authentic-pilot freshness.
- Quarantined sources remain countable only as aggregates.
- `MERGE_AUTHORIZATION = NOT_GRANTED`

## Validation

```
pytest tests/unit/test_as_mvp_001_freshness_truth.py \
       tests/unit/test_as_val_001_freshness_orphan.py \
       tests/integration/test_as_mvp_001_portfolio.py \
       tests/integration/test_as_mvp_001_release_closure.py --no-cov
```
