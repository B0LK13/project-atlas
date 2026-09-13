# AT3-048-F4 — forged Truth Core authority is not a search hit

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `search_memory` echoed `item.authority` into hits and
`persist_search` wrote that label unchanged. A memory observation carrying
`authority: TRUTH_CORE` searched successfully, reported
`provenance_preserved: True`, and persisted `TRUTH_CORE`.

Reproduced on exact main HEAD:

```text
hit.authority = TRUTH_CORE
provenance_preserved = True
persisted authority = TRUTH_CORE
```

Distinct from #832 / #836 / #837 (project_id binding) and from #867
(capability `security_class="AUTHORITY"`). Consume-path
`_reject_authority_claims` in AT3-054 does not cover search projection.

## Fix

Memory search authority is `NON_CANONICAL` only. Missing/blank defaults to
that. `TRUTH_CORE`, owner/merge/governor/security labels, and any other
non-canonical-except-NON_CANONICAL token fail closed
(`AUTHORITY_CLAIM_FORBIDDEN`) on both search and persist. Persist writes
nothing when a hit is forged.

Does not touch `ingestion.py`. Does not change ranking or transcript-dump
rules. Does not grant merge authority.
