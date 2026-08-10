# Knowledge Time Machine — fixture plan (PREP deepen)

Status: **PREP ONLY**. Base positive payloads remain under
`docs/atlas-2.2/time-machine/fixtures/` (peer to PR #168). Negative deepen
payloads live in the same directory with `negative-*` prefix. **Gate credit:
NO.** Runner: absent until post-unlock.

## Families

| Family | Path | Package |
|---|---|---|
| time-machine (base) | `docs/atlas-2.2/time-machine/fixtures/` | AS-2.2-TIME-MACHINE-001 (peer positives) |
| time-machine deepen | `docs/atlas-2.2/time-machine/fixtures/negative-*.expect.json` | AS-2.2-TIME-MACHINE-DEEPEN-PREP-001 |

## Base scenarios (peer — do not relocate)

| ID | File | Intent |
|---|---|---|
| FX-2.2-TM-001 | `as-of-selected.sample.json` | Single-cover as-of → selected claim |
| FX-2.2-TM-002 | `as-of-overlap.expect.json` | Overlap → unresolved_overlap (no winner) |
| FX-2.2-TM-003 | `diff-t1-t2.sample.json` | Envelope with claim/graph/decision diffs |
| FX-2.2-TM-004 | `claim-diff.sample.json` | Claim added/changed/removed sketch |
| FX-2.2-TM-005 | `graph-diff.sample.json` | Derived edge add/remove (≠ authority) |
| FX-2.2-TM-006 | `decision-diff.sample.json` | Review disposition transition sketch |
| FX-2.2-TM-007 | `rejected-wall-clock.expect.json` | `as_of=now` → rejected_malformed |

## Deepen scenarios (negative)

| ID | File | Intent |
|---|---|---|
| FX-2.2-TM-101 | `negative-layer-b-promotion.expect.json` | Layer B / canonical promotion → rejected |
| FX-2.2-TM-102 | `negative-llm-authority.expect.json` | LLM authority stamp on diff → rejected |
| FX-2.2-TM-103 | `negative-silent-overlap-winner.expect.json` | Silent overlap winner → rejected |
| FX-2.2-TM-104 | `negative-pilot-invent.expect.json` | Fixture-as-authentic-pilot → rejected |
| FX-2.2-TM-105 | `negative-release-cert-stamp.expect.json` | Release-cert stamp from fixture → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `authority.level = derived` on any referenced snapshot/diff context
- Synthetic relative paths / ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- `generated` may include `by` only — never wall-clock `at`
- Never mutate runtime from fixture success
- Do not relocate or duplicate base positive fixtures

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-TM-001..007 | payload-present (base peer) | **NO** |
| FX-2.2-TM-101..105 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
