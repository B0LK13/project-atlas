# AT3-081-F2 — conflicts and nested reconciliation must be objects

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

Independent IV of AT3-081-F1 (#833) recorded two residuals on live main:
`reconciliation.conflicts` as a list/string was ignored (compose fell
through to `detect_conflicts`), and a non-dict `reconciliation` value
silently fell back to the parent object.

## Fix

Non-object `conflicts` and non-object nested `reconciliation` raise
`RECONCILE_CORRUPT`. Flat artifacts without a `reconciliation` key still
compose from the parent object.

Does not touch `ingestion.py`. Does not widen #833.
