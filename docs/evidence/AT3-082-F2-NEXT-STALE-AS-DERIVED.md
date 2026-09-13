# AT3-082-F2 — stale next-action must not compose as derived

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `compile_next_action_honesty` rejected `freshness=STALE`
only when `status` was CURRENT/verified. A Pulse next block with
`status=derived` and `freshness=STALE` composed as `status=derived`,
`next="stale next action"`, `stale_as_current=False`.

## Fix

Any `freshness=STALE` next payload fails closed (`STALE_AS_CURRENT`),
including empty status (ADV residual on the first F2 object). Fresh
derived next still composes.

Distinct from #869 (Pulse `_from_answer`) and #845 (project-scope bind).
Overlaps #845 on `next_honesty.py`.
