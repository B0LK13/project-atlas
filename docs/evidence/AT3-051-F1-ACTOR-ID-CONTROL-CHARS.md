# AT3-051/052-F1 — control characters cannot disguise implementer as verifier

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `verifier_id="implementer\\x00"` and `adv_id="model\\x00"`
bound successfully because the forbidden-actor check compared the full
string (with NUL) and never matched `implementer` / `model`.
`implementer_is_verifier` / `implementer_is_adv` stayed False.

## Fix

IV and ADV actor ids containing any C0 control character (including NUL)
fail closed (`VERIFIER_ID_INVALID` / `ADV_ID_INVALID`) before the
forbidden-name check. Plain `implementer` / `model` still fail as before.

Does not grant merge or security certification.
