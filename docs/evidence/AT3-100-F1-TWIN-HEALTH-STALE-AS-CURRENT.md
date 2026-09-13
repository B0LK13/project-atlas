# AT3-100-F1 — twin health must not treat stale signals as current

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, a declared signal with `state=CURRENT` plus `freshness=STALE`,
`stale_as_current=true`, and `unverified=true` compiled as `status=derived`
with the CURRENT state preserved. `_signals()` only validated `state` against
ALLOWED_STATES and dropped contradictory honesty flags.

## Fix

`freshness=STALE` with `state=CURRENT`, explicit `stale_as_current`, and
`unverified` + verified/current fail closed. Honest CURRENT signals still
derive. Distinct from #869/#871.
