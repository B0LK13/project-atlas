# AT3-091-F1 — Timeline refuses wall-clock as declared valid-time

- Package: `AT3-091-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- LLM OUTPUT != AUTHORITY
- TIMELINE != TRUTH CORE
- Wall-clock / observed_at is not valid-time

## Finding

`compile_timeline` orders ledger rows by document-declared valid-time.
`_valid_key()` only rejected `wall_clock_is_valid_time is True`. A caller
could:

1. pass `wall_clock_is_valid_time="true"` / `1` and still get
   `temporal_status: "declared"`
2. copy `observed_at` into `valid_time` (same ISO string) and have the
   timeline sort and label that wall-clock as declared valid-time

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

```
wall-clock smuggle declared 2026-09-13T22:00:00Z
string-true flag: NO RAISE
```

Distinct from #875 (Time Machine STALE-as-current) and from the
`live_full_history_sync="true"` residual class (different field, different
module). This is temporal valid-time vs wall-clock on the timeline read path.

## Remediation

`_valid_key` fail-closes on truthy wall-clock flags and when a non-empty
`valid_time` / `valid_from` equals `observed_at`. Honest `valid_from`
without `observed_at` still orders as declared.

## Out of scope

- `ingestion.py` (F5-B freeze)
- Time Machine UX (#875)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
