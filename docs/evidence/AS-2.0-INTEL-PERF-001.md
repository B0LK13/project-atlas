# AS-2.0-INTEL-PERF-001 — Dense-group pairing optimization

## Purpose

Track and reduce the Wave-1 MAJOR residual: intra-slot contradiction
pairing was O(k²) over every claim in a subject+field group, including
same-value pairs that can never be candidates.

## Truth boundary

Semantics are unchanged. Same-value, UNKNOWN, succession, and
cross-project pairs still produce no candidate. Candidate ids remain
deterministic.

## Algorithm

1. Prepare each claim once (normalized value, lineage, evidence refs).
2. Drop UNKNOWN before grouping.
3. Group by project + subject + field.
4. Partition each group by normalized value.
5. Pair only across different value partitions.
6. Build a source index once.

Complexity: `O(N + Σ_{groups} Σ_{i<j} |A_i|·|A_j|)` where `A_i` are
value partitions. Same-value pairs are not evaluated.

## Failure modes

- Dense groups with many distinct incompatible values still emit many
  candidates; that is semantic, not a defect.
- Never drop a qualifying pair to save time.

## Test results

Recorded after implementation. See package tests.
