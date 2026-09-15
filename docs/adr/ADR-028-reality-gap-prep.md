# ADR-028 — Reality Gap prep (Atlas 2.2)

| Field | Value |
|---|---|
| Status | **Accepted (prep boundary)** |
| Date | 2026-08-10 |
| Package | AS-2.2-REALITY-GAP-PREP-001 |
| Baseline tip | `a1e0972` / TREE `c6cfe95` |
| Unlock | After `v2.1.0` + `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` |

## Context

Atlas already ships fixture-safe Reality Gap inventory
(`AS-2.0-REALITY-GAP-001`) and a read-only UI catalog
(`AS-2.0-REALITY-GAP-UI-001`). Parallel 2.2 capacity before `v2.1.0` must remain
architecture / contracts / fixtures only so 2.1 tip stability is preserved.

Operators still need an honest gap register that refuses three failure modes:

1. treating **unknown** status as **healthy**
2. letting **UI** panels become **canonical** writers
3. **inventing PILOT** roots from fixture rehearsal

## Decision

1. Seed **docs-only** Reality Gap prep architecture, JSON Schema stubs, and
   fixture sketches under `docs/atlas-2.2/reality-gap/`.
2. Keep stubs **out of** `src/project_atlas/schemas/` and out of required CI
   until `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Do **not** mutate existing `reality_gap` / `reality_gap_ui` runtime packages
   in this PREP.
4. Encode fail-closed invariants: unknown≠healthy, UI≠canonical, no PILOT invent.
5. Assert `ATLAS_2_1_RELEASE_CERTIFIED = NO` for this package's claims.

## Consequences

### Positive

- Unblocks parallel 2.2 design without destabilizing 2.1 tip
- Makes Reality Gap honesty rules reviewable before runtime exists
- Preserves 2.0 modules as the live inventory/UI substrate

### Negative / deferred

- Stubs can be mistaken for shipped schemas — mitigated by PREP markers
- Scenario vocabulary (`unknown`, `healthy=false`) awaits freeze review
- Production CLI / module not authorized in this PREP

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Extend 2.0 `reality-gap-inventory` schema in place pre-2.1 | Risks 2.1 tip / compat churn |
| Treat fixture PASS as healthy estate | Violates unknown≠healthy / no PILOT invent |
| Allow UI catalog writes for convenience | Violates UI≠canonical |

## Non-decisions

- No CLI, no Python module mutation, no release-cert claim, no PILOT waiver.

## References

- `docs/atlas-2.2/reality-gap/AS-2.2-REALITY-GAP-PREP-001.md`
- `docs/AS-2.0-REALITY-GAP-001.md`
- `docs/atlas-2.0/REALITY-GAP.md`
- `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`
