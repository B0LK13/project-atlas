# AT3-015-F2 — Pulse must not compose stale or empty answers as current truth

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, Pulse `_from_answer` copied `status` from a lens file without
checking freshness or materialization.

1. `{"freshness":"STALE","status":"verified"}` composed as
   `questions.what_changed.status = verified`.
2. `{}` composed as `status = derived` with `items: [{}]`, while a missing
   file stays `UNKNOWN`.

#843 binds foreign `project_id` only and does not add freshness or empty-object
honesty. #829 is consume-path context-compiler freshness, not Pulse compose.
#841 is `stale_conflict.py` mixed-corrupt filtering.

## Fix

Empty or non-object answers stay `UNKNOWN` (same missing reason).
`freshness=STALE` plus `status`/`disposition` of `verified` or `current`
fails closed (`STALE_AS_CURRENT`). A stale answer without those labels
reports `status=STALE`, never `derived`/`verified`.

Overlaps `#843` on `pulse.py` / `_from_answer`. Distinct semantic package.
Does not edit `start.py`. Does not touch `ingestion.py`.
MERGE_AUTHORIZATION remains NOT_GRANTED.
