# Ask Atlas 2 deepen — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/ask-atlas-2/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| ask-atlas-2 | `docs/atlas-2.2/ask-atlas-2/fixtures/` | AS-2.2-ASK2-DEEPEN-PREP-001 |

Unique vs research-ask2 fixtures under
`docs/atlas-2.2/fixtures/research/` — this family does **not** relocate or
overwrite those peers.

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-ASK2-001 | `deepen-answer-complete.sample.json` | Deepen view with citation + lenses |
| FX-2.2-ASK2-002 | `citation-chain.sample.json` | Evidence→hypothesis→pack chain |
| FX-2.2-ASK2-003 | `lens-projection-web.sample.json` | Web lens projection |
| FX-2.2-ASK2-004 | `negative-live-mutate.expect.json` | live mutate → rejected |
| FX-2.2-ASK2-005 | `negative-llm-authority.expect.json` | LLM authority stamp → rejected |
| FX-2.2-ASK2-006 | `negative-canonical-write.expect.json` | canonical write → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never mutate runtime `ask_atlas_live` from fixture success

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-ASK2-001..006 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
