# AT3-040-F2 — planned/intent language is not a current-state claim

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `_classify` mapped planned+claim text
("Migration to PostgreSQL 16 remains planned",
"we should migrate production postgres later") to `claim_candidate`.
Intent language was extracted as current state. INTENT != CURRENT STATE
was violated at the extractor.

## Fix

Planned+claim text becomes `proposed_decision`, or `next_step` when next-
action language is also present. Bare current claims without plan language
remain `claim_candidate`.

`after` is not treated as plan language by itself (present-tense
"uses PostgreSQL 15 after …" stays `claim_candidate`).

Distinct from #847 (mixed-project extract batches) on the same file.
Does not grant merge authority.
