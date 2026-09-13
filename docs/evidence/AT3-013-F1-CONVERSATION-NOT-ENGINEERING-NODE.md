# AT3-013-F1 — Conversation is not an engineering twin node

- Package: `AT3-013-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- CONVERSATION != TRUTH
- LLM OUTPUT != AUTHORITY
- GRAPH != AUTHORITY

## Finding

`compile_engineering_nodes` mapped `COMMIT_CREATED` / `PR_*` / `TEST_*` /
`BUILD_*` with no source or authority-class gate. Empty `evidence_refs`
were replaced with a circular `ledger:{event_id}` self-ref. `make_node`
then stamped `authority="derived"`.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

A `conversation_capture` + `authority_class="non-canonical"` commit row
with empty evidence became a derived commit node whose only provenance
was the invented ledger self-ref.

Distinct from #872 (blank evidence_ref treated as present on proof) and
from ledger append/hash verify (#830/#864/#865). This is class
escalation plus invented provenance on the AT3-013 projection.

## Remediation

Skip `source=conversation_capture` and `authority_class=non-canonical`
before minting nodes. Honest engineering-plane events still project.

## Out of scope

- Invented `ledger:{id}` fallback for honest engineering rows (existing contract)
- `ingestion.py` (F5-B freeze)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
