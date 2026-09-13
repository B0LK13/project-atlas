# AT3-044-F1 — stale stronger evidence must not mint CURRENT

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `classify_freshness` treated matching PostgreSQL evidence as
CURRENT even when that evidence was `freshness=STALE`, `freshness=UNKNOWN`,
or `historical=True`. Historical memory minted current truth.

## Fix

Matching stronger-evidence rows that are STALE, UNKNOWN, CONTESTED, or
historical cannot return CURRENT. Contradiction against any versioned row
still returns STALE. Unspecified freshness on stronger evidence remains
CURRENT (existing contract).

Distinct from presentation-layer STALE-as-current packages (#869/#871/#873/#875/#876).
Does not grant merge authority.
