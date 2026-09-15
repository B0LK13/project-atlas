# Governed agent memory — fixture plan (PREP deepen)

Status: **PREP ONLY**. Base positive payloads remain under
`docs/atlas-2.2/fixtures/mem-gov/` (peer to PR #169). Negative deepen payloads
live under `docs/atlas-2.2/mem-gov/fixtures/`. **Gate credit: NO.** Runner:
absent until post-unlock.

## Families

| Family | Path | Package |
|---|---|---|
| mem-gov (base) | `docs/atlas-2.2/fixtures/mem-gov/` | AS-2.2-MEM-GOV-001 (peer) |
| mem-gov deepen | `docs/atlas-2.2/mem-gov/fixtures/` | AS-2.2-MEM-GOV-DEEPEN-PREP-001 |

## Deepen scenarios (negative)

| ID | File | Intent |
|---|---|---|
| FX-2.2-MEM-101 | `negative-layer-b-promotion.expect.json` | Layer B / canonical promotion → rejected |
| FX-2.2-MEM-102 | `negative-llm-authority.expect.json` | LLM authority stamp → rejected |
| FX-2.2-MEM-103 | `negative-dual-active.expect.json` | dual-active fork without supersession → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `authority_plane = none` on any referenced memory context
- Synthetic relative paths / ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- `generated` may include `by` only — never wall-clock `at`
- Never mutate runtime from fixture success
- Do not relocate or duplicate base positive fixtures from `fixtures/mem-gov/`

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-MEM-101..103 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
