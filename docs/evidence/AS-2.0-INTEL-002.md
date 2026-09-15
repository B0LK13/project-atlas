# AS-2.0-INTEL-002 — Contradiction Candidate Intelligence

## Purpose

Read-only detection of explainable contradiction *candidates* over
existing claims, valid-time windows, authority, and lineage. Built on
AS-2.0-INTEL-001. A candidate is a review signal, not a verdict.

## Truth boundary

```
AUTO_RESOLVE_CONTRADICTIONS = NO
AUTO_DELETE_LOSING_CLAIM = NO
AUTO_WRITE_CANONICAL = NO
CONTRADICTION_CANDIDATE_IS_PROVEN_FALSEHOOD = NO
DERIVED_INTELLIGENCE_IS_AUTHORITY = NO
```

## Data model

`ContradictionCandidate` records:

- deterministic `candidate_id`
- class (`value-conflict`, `temporal-conflict`, `authority-conflict`,
  `source-divergence`, `scope-conflict`, `identity-ambiguity`,
  `unknown-conflict`)
- claim pair (sorted ids), subject, field, project
- temporal / authority / source relationships
- severity class (not a probability)
- reason, evidence refs, uncertainty, human-review recommendation

## Algorithm

1. Group claims by `(project_id, subject, field)`. Never pair across
   projects, subjects, or fields.
2. Sort each group by `claim_id`. Compare only intra-group pairs.
3. Skip: UNKNOWN values, UNKNOWN confidence, equal normalized values,
   different explicit authority domains, proven succession, proven
   non-overlapping windows.
4. Classify remaining pairs with specific classes first (identity,
   same-lineage divergence, overlapping valid-time, scope, authority,
   then value / unknown).
5. Sort output by `candidate_id`. Input order cannot change semantics.

Complexity: `O(N + Σ k_i²)` where `k_i` is the size of group `i`,
not `O(N²)` over the whole vault.

## Failure modes

- Missing windows → temporal relationship `unknown`; may still emit a
  value-conflict with uncertainty, never a false temporal contradiction.
- Missing source records add uncertainty; they do not delete claims.
- Identity ambiguity is reported only when the caller marks it.

## Security impact

Read-only. No new auth scope. No vault writes.

## Migration impact

None. Additive optional `authority_domain` on `AssessableClaim` only.

## Known limitations

- Independence of sources is still unknown (Package 1 invariant).
- Domain authority registry rules are not re-evaluated here; callers may
  pass `authority_domain` when they know it.

## Rollback

Remove `contradictions.py` and Package 2 tests/docs. Package 1 remains.

## Test results

```
AS_2_0_INTEL_002 = PASS
FALSE_TEMPORAL_CONTRADICTION = 0
CROSS_PROJECT_FALSE_CONTRADICTION = 0
UNKNOWN_FALSE_CONTRADICTION = 0
DETERMINISTIC = YES
MUTATION = NO
PACKAGE_2_RUFF = PASS
PACKAGE_2_MYPY = PASS
```

Covered: simultaneous incompatible values, formatting-only sameness,
March→October succession, overlapping validity, non-overlapping
validity, same lineage, different authority domains, different
projects, strong vs weak, UNKNOWN vs known, missing source,
identity ambiguity, replay/order.

## Future API contract

Draft only: `GET /v1/intelligence/conflicts`. Not registered.
