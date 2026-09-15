# Conflict UX — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/conflict-ux/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| conflict-ux | `docs/atlas-2.2/conflict-ux/fixtures/` | AS-2.2-CONFLICT-UX-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-CUX-001 | `cockpit-open-conflict.sample.json` | Cockpit view with one open card |
| FX-2.2-CUX-002 | `projection-card-duplicate-source.sample.json` | Card with duplicate-source facet |
| FX-2.2-CUX-003 | `review-queue-slice.sample.json` | CONFLICT queue slice (same root) |
| FX-2.2-CUX-004 | `negative-auto-resolve.expect.json` | `auto_resolve` → rejected |
| FX-2.2-CUX-005 | `negative-ui-write.expect.json` | UI canonical write → rejected |
| FX-2.2-CUX-006 | `negative-authority-elevation.expect.json` | authority elevation → rejected |

Deepen certification / PILOT / LLM negatives are inventoried in
[`DEEPEN-FIXTURE-PLAN.md`](DEEPEN-FIXTURE-PLAN.md) (FX-2.2-CUX-101..103).

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never mutate runtime `conflict_projections` from fixture success

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-CUX-001..006 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
