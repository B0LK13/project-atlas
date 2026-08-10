# ADR-2.2-DOD-001 — Definition-of-Done compiler prep

| Field | Value |
|---|---|
| Status | **Accepted (prep boundary)** |
| Date | 2026-08-10 |
| Package | AS-2.2-DOD-COMPILER-001 (PREP) |
| Deciders | Atlas program (autonomous prep under forced multi-agent orchestration) |

## Context

Atlas 2.1 tip is release-hardening against authentic PILOT. Parallel capacity
must not invent 2.1 busywork. Validated 2.2 P1 work may land as
**contracts/fixtures/ADRs only** before `v2.1.0`, without dependency-bearing
production mutation.

Operators need a future compiler that turns Goals into proof receipts along:

`Goal → DoD → criteria → tests → evidence → proof`

## Decision

1. Seed **docs-only** DoD compiler architecture, JSON Schema stubs, and fixture
   sketches under `docs/atlas-2.2/`.
2. Keep stubs **out of** `src/project_atlas/schemas/` and out of required CI
   until `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Encode fail-closed evidence-class rules so fixture receipts cannot satisfy
   `authentic_pilot` criteria.
4. Proof receipts are consume-only and never promote Layer B authority.

## Consequences

- Positive: unblocks parallel 2.2 design without destabilizing 2.1 tip.
- Positive: makes “done” claims auditable before runtime exists.
- Negative: stubs can be mistaken for shipped schemas — mitigated by PREP
  markers and non-claims in package card.

## Non-decisions

- No CLI, no Python module, no release-cert claim, no PILOT waiver.
- No sole-write of shared `docs/atlas-2.2/README.md` in this package (siblings
  also prep under the same tree).
