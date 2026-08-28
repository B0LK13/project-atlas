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
frozen binding to the current manifest identity. Resume recomputes live
freshness. A forged on-disk `freshness` field is not authority. When the
frozen binding is not current, resume emits `resume_warning` (human CLI
prints `warning:`; `--json` includes the field).

D-183 recert against live main `6709ad7751f2135b507b74013808ecfe2198a3a3`.
D-185: rebound onto post-#474 main `b2d15866622c31efd0999b320e16340711d3dba6`.
Missing or malformed `estate_binding` is UNKNOWN / not-current and never
inherits live FRESH.

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
- CLI surfaces computed resume freshness + `resume_warning` only; it does
  not mint authority
- Binding metadata is not Truth Core and is not authority
