# AT3-030-F2 — Start must not present a stale state lens as current truth

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `compile_start(..., freshness_requirement="CURRENT")` treated a
state lens `{"freshness":"STALE","status":"verified","summary":"..."}` as
`current_verified_truth` with `status=derived` and
`stale_presented_as_current=False`.

An empty `{}` state file was also treated as a present lens
(`"state lens present"` / `derived`).

#844 binds foreign `project_id` on `ans-state` / `ans-decisions` only.
It does not add freshness honesty. Pulse-compose `STALE+verified` into
`recent_material_changes` is AT3-015-F2 / #869.

## Fix

Empty/non-object state is treated as missing (UNKNOWN). A `freshness=STALE`
state lens fails closed (`STALE_AS_CURRENT`) when the caller asked for
`CURRENT` or the file claims `verified`/`current`. Fresh derived state still
composes.

Overlaps `#844` on `start.py`. Distinct semantic package.
Does not edit `pulse.py` or `ingestion.py`.
