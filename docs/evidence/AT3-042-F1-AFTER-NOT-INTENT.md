# AT3-042-F1 — present-tense "after" is not intent

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `detect_conflicts` treated `\bafter\b` as intent language.
A current-state claim "production uses PostgreSQL 16 after the rollback"
was filed under `intent_versions` and `conflicted_history` stayed False
against current PostgreSQL 15.

## Fix

`after` is no longer intent language by itself. Planned/later/migrate
still classify as intent. Present-tense after-claims stay observed
versions so 15-vs-16 conflicts remain visible.

Distinct from #849 (mixed-project batches) and #877 (extractor).
Does not grant merge authority.
