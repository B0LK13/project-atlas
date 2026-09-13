# AT3-048-F3 — persist_search binds result.project_id

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

Independent IV of AT3-048-F2 (#836) recorded that a caller envelope with
no/empty `hits` and `project_id: other-api` still persisted under
`harbor-api`. The hits[*] guard does not see a missing hits list.

## Fix

If `result.project_id` is present and non-blank, it must match the persist
target or the write is refused (`PROJECT_MISMATCH`).

Does not touch `ingestion.py`. Does not widen #832 or #836.
