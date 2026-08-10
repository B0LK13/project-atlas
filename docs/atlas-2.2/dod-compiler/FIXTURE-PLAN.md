# DoD compiler — fixture plan (PREP)

Status: **PREP ONLY** — sketches + small JSON payloads for review.
Not a runnable harness. Gate credit: **none**.

## Family

| Family | Path | Mutates vault? |
|---|---|---|
| dod-compiler | `docs/atlas-2.2/fixtures/dod-compiler/` | **no** |

## Scenarios

| ID | Intent | Expected proof |
|---|---|---|
| FX-2.2-DOD-001 | Complete chain with unit_test evidence | `PASS` |
| FX-2.2-DOD-002 | Criterion missing evidence ref | `INCOMPLETE` |
| FX-2.2-DOD-003 | Fixture evidence offered for authentic_pilot criterion | `FAIL` (class mismatch) |
| FX-2.2-DOD-004 | Test binding points at unknown criterion_id | `FAIL` |

## Inventory

| File | Scenario | Notes |
|---|---|---|
| `sample-goal.json` | shared | Goal stub |
| `sample-dod-chain.json` | FX-2.2-DOD-001 | Full chain input sketch |
| `expected-proof-pass.json` | FX-2.2-DOD-001 | PASS shape |
| `expected-proof-incomplete.json` | FX-2.2-DOD-002 | INCOMPLETE shape |
| `expected-proof-fail-evidence-class.json` | FX-2.2-DOD-003 | FAIL class mismatch |
| `README.md` | — | Family policy |

## Non-credit

- Payload presence ≠ coverage
- Fixture PASS ≠ authentic PILOT
- No CI job may treat these as release gates before unlock + freeze
