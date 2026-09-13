# AT3-048-F2 — persist_search binds hits to requested project

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

`persist_search` wrote a caller-supplied result under
`generated/ops/atlas3/memory/<requested-project>/search.json` without
checking `hits[*].project_id`. A result whose hit was `other-api`
persisted under `harbor-api`. Distinct from AT3-048-F1 (#832), which
covers `search_memory` only.

## Fix

Require every hit to carry a non-blank `project_id` matching the persist
target. Missing or foreign hits fail closed (`PROJECT_MISMATCH`) and
write nothing.

Does not touch `ingestion.py`. Does not widen #832.
