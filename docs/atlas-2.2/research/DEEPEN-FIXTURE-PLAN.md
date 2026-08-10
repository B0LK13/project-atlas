# Research workspace — fixture plan (PREP deepen)

Status: **PREP ONLY**. Base positive payloads remain under
`docs/atlas-2.2/fixtures/research/` (peer to PR #171). Negative deepen payloads
live under `docs/atlas-2.2/research/fixtures/`. **Gate credit: NO.** Runner:
absent until post-unlock.

## Families

| Family | Path | Package |
|---|---|---|
| research (base) | `docs/atlas-2.2/fixtures/research/` | AS-2.2-RESEARCH-001 (peer) |
| research deepen | `docs/atlas-2.2/research/fixtures/` | AS-2.2-RESEARCH-DEEPEN-PREP-001 |

## Deepen scenarios (negative)

| ID | File | Threat row | Intent |
|---|---|---|---|
| FX-2.2-RES-101 | `negative-hypothesis-promotion.expect.json` | T-2.2-RES-001 | Hypothesis → Layer B winner → rejected |
| FX-2.2-RES-102 | `negative-silent-winner.expect.json` | T-2.2-RES-002 | Silent conflict pick → rejected |
| FX-2.2-RES-103 | `negative-llm-authority.expect.json` | T-2.2-RES-005 | LLM authority stamp → rejected |
| FX-2.2-RES-104 | `negative-class-mismatch.expect.json` | T-2.2-RES-004 | `fixture_receipt` for `authentic_estate` → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `authority_promoted = false` on any referenced workspace context
- Synthetic relative paths / ids only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS / unlock YES
- `generated` may include `by` only — never wall-clock `at`
- Never mutate runtime from fixture success
- Do not relocate or duplicate base positive fixtures from `fixtures/research/`

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-RES-101..104 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
