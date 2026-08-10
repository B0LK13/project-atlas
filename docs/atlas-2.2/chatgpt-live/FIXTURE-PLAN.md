# ChatGPT Live — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/chatgpt-live/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| chatgpt-live | `docs/atlas-2.2/chatgpt-live/fixtures/` | AS-2.2-CHATGPT-LIVE-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-CGL-001 | `live-bridge-request.sample.json` | Explicit opt-in live request |
| FX-2.2-CGL-002 | `quarantine-envelope.sample.json` | Mandatory quarantine envelope |
| FX-2.2-CGL-003 | `live-session-quarantined.sample.json` | Session receipt after quarantine |
| FX-2.2-CGL-004 | `negative-bypass-quarantine.expect.json` | Bypass quarantine → rejected |
| FX-2.2-CGL-005 | `negative-layer-b-write.expect.json` | Layer B write → rejected |
| FX-2.2-CGL-006 | `negative-llm-authority.expect.json` | LLM authority stamp → rejected |
| FX-2.2-CGL-007 | `negative-default-on-live.expect.json` | Default-on live → rejected |
| FX-2.2-CGL-008 | `negative-pilot-invent.expect.json` | PILOT invent → rejected |
| FX-2.2-CGL-009 | `synthetic-transcript.sample.json` | Synthetic turn transcript (no network) |
| FX-2.2-CGL-010 | `negative-missing-env.expect.json` | Missing env credential → rejected |
| FX-2.2-CGL-011 | `negative-billing-blocked.expect.json` | Billing gate → rejected before API call |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data / API keys in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never mutate runtime `chatgpt_bridge` from fixture success

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-CGL-001..011 | payload-present (docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
