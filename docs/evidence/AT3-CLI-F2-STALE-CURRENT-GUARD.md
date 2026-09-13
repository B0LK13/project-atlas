# AT3-CLI-F2 — memory stale must not dump CURRENT-tagged rows

- Package: `AT3-CLI-F2`
- Follow-on to: `AT3-CLI-F1` on `#861`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Prior HEAD: `05a0c4facd8f9bcddda22c674209a6116eabd075`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- STALE != CURRENT

## Finding

`compile_stale_conflict_intel` fail-closes when `stale_memories` contains
`freshness: CURRENT`. The CLI `atlas memory stale` path loaded the same
list (after F1 artifact binding) and dumped it after only
`assert_items_project_scope`. A poisoned `reconcile.json` made the CLI
report CURRENT-tagged items as stale inventory with exit 0.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

```
stale_conflict_guard_failed_closed: STALE_AS_CURRENT
cli_exit_code: 0
cli_first_freshness: CURRENT
```

Distinct from F1 (corrupt-as-absent) and from STALE-as-current Start/Pulse
clones. This is a CLI bypass of the AT3-081 freshness guard.

## Remediation

After project-scope assert, the CLI raises `STALE_AS_CURRENT` when any
stale row is tagged CURRENT. Honest STALE rows still dump.

## Out of scope

- `ingestion.py` (F5-B freeze)
- `stale_conflict.py` (already guarded; do not duplicate)
- `read_json` global behavior
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
