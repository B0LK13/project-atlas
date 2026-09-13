# AT3-048-F4 — memory reconcile consume path fails closed

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `atlas memory search|context|conflicts` treated a non-object
`reconciliation` as an AttributeError (`list/str.get`) and treated unreadable
or array `reconcile.json` as a healthy zero-hit search.

## Fix

`load_memory_reconcile` requires the project to exist, then distinguishes
missing (empty) from corrupt (fail closed).
Nested `reconciliation` / `items` / `conflicts` / `stale_memories` must be the
declared shapes. Mixed valid+corrupt items fail closed.

Does not touch `search_memory` or `persist_search` (#832/#836/#837).
Does not touch `ingestion.py`.
