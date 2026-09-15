# Live Reality Gap collectors — fixture plan (PREP deepen)

Status: **PREP ONLY**. Base positive payloads remain under
`docs/atlas-2.2/reality-live/fixtures/` (peer to PR #167). Negative deepen payloads
live in the same directory alongside base positives. **Gate credit: NO.** Runner:
absent until post-unlock.

## Families

| Family | Path | Package |
|---|---|---|
| reality-live (base) | `docs/atlas-2.2/reality-live/fixtures/planes.fixture.json`, `collectors.fixture.json` | AS-2.2-REALITY-LIVE-001 (peer) |
| reality-live deepen | `docs/atlas-2.2/reality-live/fixtures/negative-*.expect.json` | AS-2.2-REALITY-LIVE-DEEPEN-PREP-001 |

## Deepen scenarios (negative)

| ID | File | Intent |
|---|---|---|
| FX-2.2-RL-101 | `negative-pilot-invent.expect.json` | PILOT root invent → rejected |
| FX-2.2-RL-102 | `negative-llm-authority.expect.json` | LLM / conversational authority stamp → rejected |
| FX-2.2-RL-103 | `negative-release-cert-stamp.expect.json` | RELEASE / WEB ACCEPTED stamp from gap report → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `authority.level = derived` on any referenced gap report context
- Synthetic relative paths / ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- `generated` may include `by` only — never wall-clock `at`
- Never mutate runtime from fixture success
- Do not relocate or duplicate base positive fixtures

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-RL-101..103 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
