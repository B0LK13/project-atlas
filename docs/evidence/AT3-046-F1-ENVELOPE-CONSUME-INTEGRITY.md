# AT3-046-F1 — Incremental consume validates envelope identity

- Package: `AT3-046-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- EVENT LEDGER / ENVELOPE != TRUTH CORE

## Finding

`apply_local_incremental` treated any `envelope_id` starting with `a3ce-`
as a stable cursor token. It did not recompute identity from
provider / conversation_id / message_id / content_hash, and it did not
check `schema` or bind `content_hash` to `content_reference`.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

A poison row that kept a real `a3ce-*` id, forged `content_hash` /
`schema` / `content_reference`, and already carried the requested
`project_id` / `conversation_id` was applied. The authentic envelope
was then `skipped_already_accepted`.

Distinct from mixed-project persist (#846/#847) and from live-sync /
credential refusals already in AT3-046.

## Remediation

`verify_envelope` fail-closes on schema mismatch, malformed hash,
short-reference hash mismatch, and envelope_id not bound to
provider/ids/content_hash. Incremental consume calls it before apply.

## Out of scope

- Live provider incremental sync (EXTERNAL_BLOCKED)
- `ingestion.py` (F5-B freeze)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
