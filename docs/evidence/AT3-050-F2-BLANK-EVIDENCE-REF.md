# AT3-050-F2 — blank evidence_ref is not independent proof

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `evaluate_proof` treated a whitespace-only `evidence_ref`
as PRESENT because `raw.get("evidence_ref")` is truthy for `"   "`.
Eight blank stages produced `chain_status=PROVEN`.

## Fix

`evidence_ref` is stripped. Blank/empty refs stay UNKNOWN. A model claim
with only blank refs is `UNPROVEN_MODEL_CLAIM`, never PROVEN.

Distinct from #831 (non-object evidence) and #839 (project-scope persist).
Does not grant merge authority.
