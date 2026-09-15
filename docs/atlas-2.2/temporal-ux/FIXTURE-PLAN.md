# Temporal UX — fixture plan (PREP)

Package: **AS-2.2-TEMPORAL-UX-PREP-001**  
Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/temporal-ux/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| temporal-ux | `docs/atlas-2.2/temporal-ux/fixtures/` | AS-2.2-TEMPORAL-UX-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-TUX-001 | `cockpit-as-of-selected.sample.json` | Cockpit view with selected as-of card |
| FX-2.2-TUX-002 | `validity-window-card.sample.json` | Card with declared valid-time window |
| FX-2.2-TUX-003 | `as-of-lens-receipt.sample.json` | As-of lens receipt (selected) |
| FX-2.2-TUX-004 | `negative-wall-clock.expect.json` | wall-clock as-of → rejected |
| FX-2.2-TUX-005 | `negative-silent-winner.expect.json` | silent_winner → rejected |
| FX-2.2-TUX-006 | `negative-bitemporal-mutation.expect.json` | bitemporal_mutation → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never mutate runtime `bitemporal` from fixture success

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-TUX-001..006 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.

## Deepen PREP

See `AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md` and deepen negatives under `fixtures/`.
