# AS-CORE-002 — Verification Remediation Record

## Findings

Agent Two independently reproduced two blockers against `575ce3b`:

1. `semantic-records.schema.json` accepted invalid nested source and coverage
   values that Pydantic rejected.
2. `state/sources.json` accepted unknown schema versions and malformed source
   entries, then propagated them into tombstone state.

The review also identified a transaction-safety risk: a malformed marker in a
later project could be discovered after an earlier project's files had already
been written.

## Remediation

Commit `bb2a713`:

- adds strict item schemas for persisted semantic records, including source
  lifecycle, authority, coverage, event, validation, decision and relationship
  records, with references to existing Core schemas;
- validates `state/sources.json` schema version and every entry through
  `SourceLifecycleRecord` before ingestion proceeds;
- preflights generated markers for every affected project before source,
  state, report or projection writes;
- adds regression tests for invalid nested schema data, corrupt lifecycle
  state, and cross-project marker failure isolation.

## Checkpoint evidence

| Check | Result |
|---|---:|
| Focused schema/lifecycle/remediation tests | 13 passed |
| Full Core suite | 86 passed |
| Ruff | passed |
| Mypy | no issues in 28 source files |

Status remains `AS-CORE-002 IMPLEMENTATION COMPLETE — CERTIFICATION PENDING`
until Agent Two independently verifies `bb2a713`.
