# AT3-050-F2 — proof persist is project-bound

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

`evaluate_proof` used `safe_project_id` (not `require_project`) and wrote
`generated/ops/atlas3/proof/<task-id>.json`. A second project with the same
task id overwrote the first project's evidence. An unknown project still wrote.

## Fix

Require the project to exist. If the documented task-id file already belongs to
another project, refuse (`PROJECT_MISMATCH`) and leave bytes unchanged.

Does not change the documented path. Does not widen #831 (non-object evidence).
Does not touch `ingestion.py`.
