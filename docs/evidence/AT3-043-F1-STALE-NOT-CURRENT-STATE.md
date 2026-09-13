# AT3-043-F1 — stale memory must not land in current_state

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `extract_intent_report` classified `freshness=STALE`
`claim_candidate` / `observation` as `layer=current_state` and stripped
freshness from the output row. The honesty wrapper then reported
`stale_is_current=False` while composing stale text as current state.

## Fix

STALE items in a current-state type fail closed (`STALE_AS_CURRENT`).
STALE plus `present_as_current=True` also fails closed. STALE intent
(`next_step`) remains intent and preserves the freshness field.

Does not edit `honesty.py` (#857). The wrapper inherits the refusal.
Does not grant merge authority.
