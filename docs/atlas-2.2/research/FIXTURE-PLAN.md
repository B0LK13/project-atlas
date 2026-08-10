# Research workspace — fixture plan (PREP)

Status: **PREP ONLY** — sketches + small JSON payloads for review.
Not a runnable harness. Gate credit: **none**.

## Family

| Family | Path | Mutates vault? |
|---|---|---|
| research | `docs/atlas-2.2/fixtures/research/` | **no** |

## Scenarios

| ID | Intent | Expected outcome |
|---|---|---|
| FX-2.2-RES-001 | Complete chain with source_document evidence | Pack `COMPLETE` / Ask answer with EVIDENCE |
| FX-2.2-RES-002 | Question with no evidence refs | Pack `INCOMPLETE`; UNKNOWN populated |
| FX-2.2-RES-003 | Two hypotheses with conflicting claim pointers | Conflicts retained; no silent winner |
| FX-2.2-RES-004 | Fixture evidence offered for authentic_estate question | `FAIL` class mismatch |
| FX-2.2-RES-005 | Ask Atlas 2 answer with all eight fields | Shape valid; `canonical_write=false` |

## Inventory

| File | Scenario | Notes |
|---|---|---|
| `sample-question.json` | shared | Question stub |
| `sample-workspace-chain.json` | FX-2.2-RES-001 | Full chain input sketch |
| `expected-pack-complete.json` | FX-2.2-RES-001 | COMPLETE pack shape |
| `expected-pack-incomplete.json` | FX-2.2-RES-002 | INCOMPLETE pack shape |
| `expected-conflicts-retained.json` | FX-2.2-RES-003 | Conflict retention |
| `expected-ask-atlas-2-answer.json` | FX-2.2-RES-005 | Answer envelope |
| `README.md` | — | Family policy |

## Non-credit

- Payload presence ≠ coverage
- Fixture COMPLETE ≠ authentic PILOT
- No CI job may treat these as release gates before unlock + freeze
