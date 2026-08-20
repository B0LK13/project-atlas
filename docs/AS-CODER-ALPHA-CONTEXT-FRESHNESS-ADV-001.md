# AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001

Adversarial freshness: a context or handoff that was valid when written must
not silently appear current after the underlying project sources or
connect-manifest later change.

## Unique delta

Owner-held `#419` stamps **live** inventory freshness against the **current**
connect-manifest. After reconnect refreshes that manifest, an older pack can
look FRESH again even though it was written against a different estate.

This package stores a minimal non-authoritative `estate_binding` at write:

- sha256 of the already-written `generated/ops/connect-manifest.json`
- source digest tuples **copied from** that manifest (no second source hasher)

At read/resume it reuses `project_atlas.inventory_drift` and compares the
frozen binding to the current manifest identity.

## Honesty

- `STALE_IS_CURRENT = NO`
- `UNKNOWN_IS_CURRENT = NO`
- `UNKNOWN_IS_HEALTHY = NO`
- `FRESH_IS_AUTHORITY = NO`
- `CONTEXT_IS_AUTHORITY = NO`
- `HANDOFF_IS_AUTHORITY = NO`
- `INVENTED_FACTS = NO`
- `HARNESS != AUTHENTIC_PILOT`

## Out of scope

- Historical `#378` is not retargeted, rebased, or merged
- No second source-hash / fingerprint / ownership / manifest engine
- `inventory_drift.py` is not modified
- CLI is unchanged
- Binding metadata is not Truth Core and is not authority
