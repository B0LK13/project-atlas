# AT3-081-F1 — mixed valid + non-object memory items fail closed

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

`compile_stale_conflict_intel` built `memory_items` / `memory_stale` with
`[item for item in raw if isinstance(item, dict)]`. A reconcile artifact
containing one valid object and one non-object was treated as healthy
derived intelligence. Corruption was filtered, not refused.

## Fix

Non-object `reconciliation.items` and `stale_memories` entries raise
`RECONCILE_CORRUPT`. No partial compose.

Does not touch `ingestion.py`. Does not pick a conflict winner.
