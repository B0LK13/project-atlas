# AT3-003-F3 — verify rejects hash-valid merge authorization

- Package: `AT3-003-F3`
- Follow-on to: `AT3-003-F2` on `#865`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Prior HEAD: `4e5d003e621c8201e9da7fb7d1fa13c060d8bf52`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- EVENT LEDGER != TRUTH CORE

## Finding

`verify_engineering_event` checked schema, project, kind/type bind, and
content hash. A self-hashed row could carry `merge_authorization: GRANTED`
and `certified_for_merge: true` on the envelope and in `payload`.
`list_events` accepted it. Pulse `what_was_decided` re-emitted the row
verbatim, so a consumer could see top-level `GRANTED` next to
`honesty.merge_authorization: NOT_GRANTED`.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

```
verify_passed: True
row.merge_authorization: GRANTED
pulse.honesty.merge_authorization: NOT_GRANTED
```

Distinct from #830 (append without hash verify) and from #865 F2
(kind/event_type alias bind). Hash validity is not owner authorization.

## Remediation

`verify_engineering_event` calls `_reject_authority_claims`. GRANTED /
`certified_for_merge=True` on the row, payload, or honesty block fail
closed as `MERGE_CLAIM_FORBIDDEN`. Normalized events still verify.

## Out of scope

- `ingestion.py` (F5-B freeze)
- `pulse.py` / `start.py` (owned carriers; Pulse still composes verified rows)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
