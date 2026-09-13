# AT3-D192-PIPE-F1 — Pipeline must not persist stale accepted decisions or secrets

- Package: `AT3-D192-PIPE-F1`
- Base HEAD: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION: `NOT_GRANTED`
- STALE != CURRENT
- NFR-004 / AT-014 secrets must not appear in generated output

## Finding

`run_memory_vertical` copied every `confirmed_owner_decision` text into
`accepted_decisions` with no freshness filter, then wrote
`generated/ops/atlas3/memory/<pid>/reconcile.json`. It never called the
AT3-047 `scan_or_raise` gate.

Independently reproduced on `origin/main`
`b87b4a226f4aa8b2f669edf112aa3476454f754f`:

1. A correctly classified STALE owner line ("production is PostgreSQL 16")
   landed in persisted `accepted_decisions`. `stale_presented_as_current`
   stayed False and `next_agent_safe` stayed True.
2. `aws_secret_access_key=AKIAAAAAAAAAAAAAAAAA` in `current_state_text`
   persisted in reconcile.json.

Distinct from #829 (consume-path item freshness) and from extract's
working ingest `scan_or_raise`. Distinct from #873 (next-honesty
STALE-as-derived): this is write-path mint into `accepted_decisions`
plus a skipped secret gate.

## Remediation

Scan inputs with `scan_or_raise` before reconcile/persist. Copy only
non-STALE owner decisions into `accepted_decisions`.

## Out of scope

- Changing `next_agent_must_not_claim_pg16` (#829 compiler surface)
- `ingestion.py` (F5-B freeze)
- Truth Core writes
- merge authorization

## Validation

See the PR body for the commands actually run on the candidate object.
