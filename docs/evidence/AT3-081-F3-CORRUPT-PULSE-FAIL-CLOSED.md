# AT3-081-F3 — corrupt pulse/reconcile artifacts fail closed

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

`compile_stale_conflict_intel` used `read_json`, which returns None for
unreadable or non-object Pulse/reconcile files. A corrupt `pulse.json`
was reported as missing evidence (`UNKNOWN`) or, when ledger stale rows
existed, as a healthy `derived` composition with `pulse=None`.

## Fix

Present Pulse/reconcile files that are unreadable or not objects fail
closed (`PULSE_CORRUPT` / `RECONCILE_CORRUPT`). Missing files stay empty.

Does not change items/conflicts filtering (#833/#835).
Does not touch `ingestion.py`.
