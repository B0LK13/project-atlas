# AT3-048-F1 — missing project_id is not an unscoped search hit

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `search_memory` without a requested `project_id` discarded
empty/missing item `project_id` values before the mixed-project check.
A batch of one scoped item plus one item with no `project_id` searched
successfully and returned the unscoped item as a hit.

Reproduced: query `"secret"` against
`[{project_id: harbor-api, text: harbor postgres 15}, {text: foreign secret postgres 16}]`
returned `hit_count=1` for the foreign unscoped row.

## Fix

Require every item to carry a non-blank `project_id` even when the caller
omits requested scope. Mixed projects still fail closed. Hits now include
`project_id` so output scope is visible.

Does not touch `ingestion.py`. Does not rewrite AT3-048 ranking/transcript rules.
