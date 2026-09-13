# AT3-093-F1 — Time Machine must not compose a stale snapshot

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, a declared snapshot with `freshness=STALE` and `status=derived`
composed as `status=derived` with the valid_time kept. `_reject_authority_claims`
checked authority/wall-clock claims but not stale freshness.

## Fix

Any `freshness=STALE` on the declared payload or snapshot rows fails closed
(`STALE_AS_CURRENT`). Fresh snapshots still compose. Distinct from #873.
Empty-object-as-derived remains a separate clone class and is not this PR.
