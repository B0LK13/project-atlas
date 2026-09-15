# AS-2.0-INTEL-001 — Evidence Quality + Uncertainty Core

## Purpose

Deterministic, read-only assessment of why a claim's evidence is strong,
limited, or unknown. This is the first Intelligence Wave package.

## Truth boundary

```
EVIDENCE_ASSESSMENT_IS_AUTHORITY = NO
EVIDENCE_ASSESSMENT_MUTATES_CLAIMS = NO
EVIDENCE_ASSESSMENT_MUTATES_SOURCES = NO
EVIDENCE_ASSESSMENT_WRITES_LAYER_B = NO
DERIVED_CONFIDENCE_WRITES_TRUTH = NO
CONFIDENCE_SCORE_IS_FACT = NO
UNKNOWN_IS_VALID = YES
REPLAY_DETERMINISTIC = YES
PROVENANCE_TRACEABLE = YES
```

## Data model

Public result: `EvidenceAssessment` in `project_atlas.intelligence`.

Inputs: `Claim` or `AssessableClaim` (the latter allows missing
provenance, which the canonical `Claim` model forbids) plus an optional
`AssessmentContext` (declared sources, peer claims, validity windows,
explicit as-of valid-time).

Dimensions recorded instead of a magic score:

- source presence / count / lineage integrity
- independence (always unknown unless Atlas can prove it; path ≠ independence)
- authority class / mismatch / disagreement
- temporal applicability / staleness / not-yet-valid
- corroboration vs contradictory peers
- missing / unknown provenance
- repeated same-source observations
- durable identity after a path move

## Algorithm

1. Collect provenance and same-project same-subject+field peers.
2. Deduplicate observations by `source_lineage_id` (fallback: `source_id`).
   Repeated observations and same-lineage copies do not add corroboration.
3. Classify temporal applicability only against an explicit as-of instant.
   Wall-clock `now` / `today` fail closed.
4. Record limiting factors. Classify confidence with conservative discrete
   rules: UNKNOWN-forcing factors win, then LOW-forcing, then HIGH only
   for strong authority plus present/unknown source and stable identity.
5. Sort every list. Return a new object. Never mutate inputs.

Complexity: O(P + E) per claim for provenance and same-group peers.
Batch assessment groups peers in-memory; it does not scan the vault.

## Failure modes

- Missing provenance or explicit UNKNOWN value → UNKNOWN.
- Not-yet-valid window → UNKNOWN (not LOW).
- Stale window or contradictory peers → LOW.
- Undeclared source inventory → presence unknown, not assumed missing.
- Independence is never fabricated.

## Security impact

Read-only. No new auth scope. Evidence refs store ids / resources /
hashes, never secret-matched content.

## Migration impact

None. No schema catalog change. No vault layout change.

## Known limitations

- Source independence cannot be proven from current Atlas records.
- Observation recency is unknown unless provenance `last_modified` exists.
- Assessment does not re-run CORE-005 / CORE-006 evaluators; it consumes
  caller-supplied claims, windows, and source observations.

## Rollback

Delete `src/project_atlas/intelligence/` and the package-1 tests/docs.
No runtime registration exists.

## Test results

```
AS_2_0_INTEL_001 = PASS
PACKAGE_1_TESTS = PASS (20 focused cases)
PACKAGE_1_RUFF = PASS
PACKAGE_1_MYPY = PASS
NEW_HIGH = 0
NEW_MEDIUM = 0
```

Covered: single strong source, corroboration without fabricated
independence, same-lineage copies, authority mismatch, stale,
not-yet-valid, conflicting peers, missing provenance, missing source,
UNKNOWN honesty, unsupported claim, repeated observations, durable
identity after move, replay, no mutation, no numeric probability.

## Future API contract

Draft only: `GET /v1/intelligence/evidence` — see
`docs/contracts/AS-2.0-INTEL-WAVE1-FUTURE-API.md`. Not registered.
