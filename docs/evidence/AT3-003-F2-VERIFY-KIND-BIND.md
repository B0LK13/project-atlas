# AT3-003-F2 — verify_engineering_event binds kind to event_type

- Package: `AT3-003-F2`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- EVENT LEDGER != TRUTH CORE
- UNKNOWN stays UNKNOWN

## Finding

`normalize_engineering_event` calls `_resolve_type` and rejects
`kind=failure` + `event_type=TEST_PASSED` (`EVENT_TYPE_KIND_MISMATCH`).
`verify_engineering_event` checked schema, project, hash, and event_type
membership only. A self-hashed planted row with that mismatch verified,
listed, and was composed by Pulse as a derived failure.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

```
NORMALIZE EVENT_TYPE_KIND_MISMATCH
VERIFY ACCEPTED
LIST 1 failure TEST_PASSED
WHAT_FAILED derived ['TEST_PASSED']
```

Same class: `kind=decision` + `TEST_PASSED` made `what_was_decided` derived.

This is event-envelope alias integrity, not ledger path identity (`#864`),
not append-hash verify (`#830`), and not a declared-graph `is_file()` clone.

## Remediation

`verify_engineering_event` calls `_bind_kind_to_event_type`. Canonical kinds
in `EVENT_KINDS` must map through `KIND_TO_EVENT_TYPE`. Event types without
a kind alias keep the lowercase `event_type` normalize already stamps.

## Out of scope

- `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- `pulse.py` / `start.py` (owned carriers; Pulse still uses `kind` as an
  additional failure alias after verify has bound the row)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
