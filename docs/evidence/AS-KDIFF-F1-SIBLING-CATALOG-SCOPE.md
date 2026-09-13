# AS-KDIFF-F1 — Sibling catalogs and conflicts stay project-bound

- Package: `AS-KDIFF-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- KDIFF != AUTHORITY
- GRAPH != AUTHORITY

## Finding

`_load_windows` joined every `generated/ops/bitemporal/*.json` window
whose `claim_id` existed in the requested project's claims. A sibling
catalog minted for `proj-b` could select a `proj-a` claim that reused
the same `claim_id`. `_load_unresolved_claim_conflicts` globbed every
`review/conflicts/*.json` the same way.

Independently reproduced on live main
`b87b4a226f4aa8b2f669edf112aa3476454f754f`.

Distinct from mixed-project atlas3 persist (#846/#847) and from the
existing kdiff isolation test (different claim_ids).

## Remediation

Skip catalogs whose `catalog_id` is a sibling project id. Load only
`review/conflicts/<project_id>.json`. Shared compilation catalogs
(`kc-1`) still apply when they are not a sibling project id.

## Out of scope

- Truth Core writes
- merge authorization
- `ingestion.py`

## Validation

See the PR body for commands actually run on the candidate object.
