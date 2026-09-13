# AT3-036-F2 — ChatGPT mapping mixed valid+corrupt fail-closed

- Package: `AT3-036-F2`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- CONVERSATION != TRUTH
- UNKNOWN stays UNKNOWN

## Finding

`_preflight_json_payload` in `src/project_atlas/atlas3/memory/chatgpt.py`
walked `messages`/`turns` only. A native ChatGPT `mapping` export with no
`messages` key returned early. `parse_chat_export` then skipped non-object
mapping nodes and persisted the valid subset.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

- mapping + valid nodes + `"corrupt-not-an-object"` → 2 envelopes (fail-open)
- `messages` + valid + `"corrupt"` → `CHATGPT_EXPORT_INVALID` (already closed)

That violates AT3-039 `partial_persist_on_corrupt: False`.

Not a clone of `#864` path identity, `#865` kind bind, `#830` append verify,
declared-graph `is_file()`, or `read_json`/`load_answer`.

## Remediation

Preflight walks `mapping`. Non-object nodes and non-object `message` values
raise `CHATGPT_EXPORT_INVALID`. `message: null` empty nodes remain allowed
(native ChatGPT placeholders). Does not rewrite `openai_importer_fixtures.py`.

## Out of scope

- `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- 2.x `openai_importer_fixtures.py` rewrite
- live history APIs (EXTERNAL_BLOCKED)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
