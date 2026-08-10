# Knowledge Time Machine — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/time-machine/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| time-machine | `docs/atlas-2.2/time-machine/fixtures/` | AS-2.2-TIME-MACHINE-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-TM-001 | `as-of-selected.sample.json` | Single-cover as-of → selected claim |
| FX-2.2-TM-002 | `as-of-overlap.expect.json` | Overlap → unresolved_overlap (no winner) |
| FX-2.2-TM-003 | `diff-t1-t2.sample.json` | Envelope with claim/graph/decision diffs |
| FX-2.2-TM-004 | `claim-diff.sample.json` | Claim added/changed/removed sketch |
| FX-2.2-TM-005 | `graph-diff.sample.json` | Derived edge add/remove (≠ authority) |
| FX-2.2-TM-006 | `decision-diff.sample.json` | Review disposition transition sketch |
| FX-2.2-TM-007 | `rejected-wall-clock.expect.json` | `as_of=now` → rejected_malformed |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-TM-001..007 | payload-present (docs sketch) | **NO** |

Promotion to `fixtures/atlas-2.2/` + harness requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
