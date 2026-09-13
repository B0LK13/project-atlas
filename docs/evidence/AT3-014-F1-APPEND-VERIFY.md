# AT3-014-F1 — append_event verifies before write

- Package: `AT3-014-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- EVENT LEDGER != TRUTH CORE
- UNKNOWN stays UNKNOWN

## Finding

On live main, `append_event()` in `src/project_atlas/atlas3/ledger.py` wrote a
caller-supplied event dict after only checking `project_id`. It did not call
`verify_engineering_event` before write.

A tampered `content_hash` could be persisted. `list_events` already verifies
on read, so the poisoned row then fails closed and takes Pulse / Start with it.

Classification: write-path integrity / derived-ledger honesty. Not a Truth
Core write. Not merge authority.

## Reproduction (live main before this package)

```python
event = normalize_engineering_event(
    project_id="harbor-api",
    event_type="TEST_PASSED",
    source_plane="engineering",
    summary="unit ok",
)
event["content_hash"] = "sha256:" + "f" * 64
append_event(vault, "harbor-api", event)
# status=ok, idempotency=appended; ledger file exists with the forged hash
```

Measured on `origin/main` `b87b4a226f4aa8b2f669edf112aa3476454f754f` before
the fix: `FAIL_OPEN` with the forged hash persisted.

## Remediation

After the existing `project_id` check and before `list_events` / write:

```python
verify_engineering_event(record, expected_project_id=pid)
```

A tampered hash raises `CONTENT_HASH_MISMATCH`. The ledger file is not
created, and an existing ledger gains no new row. A valid
`normalize_engineering_event` still appends.

## Out of scope

- `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- Truth Core writes
- certified 2.x event surfaces
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
