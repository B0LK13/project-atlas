# AT3-014-F2 — payload must be an object

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `verify_engineering_event` accepted a self-consistent ledger row
whose `payload` was a JSON string (hashes rebound to match). `list_events`
returned the row. `ledger_status` reported `event_count=1`. `compile_pulse`
then raised `AttributeError: 'str' object has no attribute 'get'`.

This is invalid schema accepted as a healthy ledger, then an uncontained
Pulse crash. Distinct from AT3-014-F1 (#830), which verifies before append
but still used the same payload-blind `verify_engineering_event`.

## Fix

`verify_engineering_event` raises `LEDGER_SCHEMA_INVALID` when `payload` is
not a dict. Empty object `{}` remains valid. Pulse / ledger_status fail
closed through the existing `list_events` path.

Does not touch `ingestion.py`. Does not widen #830.
