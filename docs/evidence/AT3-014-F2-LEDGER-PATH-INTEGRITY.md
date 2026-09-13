# AT3-014-F2 — ledger path must be a regular file

- Package: `AT3-014-F2`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- EVENT LEDGER != TRUTH CORE
- UNKNOWN stays UNKNOWN

## Finding

On live main, `query_events()` / `list_events()` treated any non-file at
`generated/ops/atlas3/ledger/<project_id>.jsonl` as an empty healthy ledger
(`if not path.is_file(): return []`).

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

1. Directory at the ledger identity → `list_events` returned `[]`
   (healthy empty). `compile_ledger_observability` would then stamp
   `integrity_state=VALID` / `NO_LEDGER_EVENTS`.
2. Directory + `append_event` leaked raw `IsADirectoryError`.
3. Symlink to a planted file of valid `harbor-api` events → consumed as
   the project ledger (`planted-as-current`).
4. `append_event` wrote through that planted symlink into the target file
   outside the vault ledger identity.

This is ledger-store identity integrity (P1-B class), not a declared-graph
`is_file()` clone. The Event Ledger is evidence substrate. A replaced path
is corrupt state, not absence.

Classification: VALID P1 read/write path integrity. Not a Truth Core write.
Not merge authority.

## Remediation

`_regular_ledger_file()` fail-closes with `LEDGER_CORRUPT` when the ledger
identity is a symlink or exists and is not a regular file. Missing still
returns empty. `append_event` uses the same check before mkdir/write so it
cannot leak `IsADirectoryError` or write through a planted link.

## Out of scope

- `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- declared-graph loader `is_file()` clone sweep
- Truth Core writes
- merge authorization
- AT3-014-F1 append-hash verify (`#830`; different finding)

## Validation

See the PR body for the commands actually run on the candidate object.
