# AS-2.0-STATE-001 — Derived Project State Synthesizer

## Purpose

Read-only synthesis of an explainable current project state from claims,
evidence assessments, contradiction candidates, and valid-time windows.
This is not Roadmap and not canonical project truth.

## Truth boundary

```
PROJECT_STATE_IS_CANONICAL = NO
PROJECT_STATE_WRITES_TRUTH = NO
PROJECT_STATE_WRITES_VAULT = NO
DERIVED_STATE_WRITES_TRUTH = NO
UNSUPPORTED_STATUS_INFERENCE = 0
```

Forbidden inferred labels unless a claim value itself contains them:

- healthy
- on track
- failed
- blocked

Preferred statuses: OBSERVED, DERIVED, UNKNOWN, CONTESTED, STALE.

Invariants:

```
NO_DATA != HEALTHY
UNKNOWN != FALSE
CONTESTED != RESOLVED
STALE != INVALID
```

## Data model

`DerivedProjectState` lists known / unknown / stale / contested facts,
recent changes, open contradiction ids, evidence gaps, source-health
concerns, and attention candidates. Every fact carries claim ids,
evidence refs, limiting factors, and a why string.

## Algorithm

1. Keep only claims whose `project_id` matches the requested project.
2. Run Package 1 assessments and Package 2 candidate detection.
3. Group remaining claims by subject + field.
4. CONTESTED if candidates exist for the slot (value withheld).
5. Else if an explicit as-of selects one applicable value, use it
   (STALE if that evidence is stale).
6. Else UNKNOWN / STALE / OBSERVED / DERIVED from assessments.
7. Temporal succession is a change, not a contradiction.
8. Empty input yields one UNKNOWN `observed-claims` fact.

Complexity: assessment + grouped pairing, not whole-vault O(N²).

## Failure modes

- No data → UNKNOWN, never healthy.
- Cross-project claims are dropped, not merged.
- Health/roadmap language in synthesizer text fails closed.

## Security impact

Read-only. No new auth scope. No vault writes.

## Migration impact

None.

## Known limitations

- Does not materialize `generated/answers` lenses.
- Does not call `atlas state` or write Coder Alpha artifacts.
- Attention is explainable, not prioritized by a score.

## Rollback

Remove `derived_state.py` and Package 3 tests/docs. Packages 1–2 remain.

## Future API contract

Draft only: `GET /v1/project-state`. Not registered.
