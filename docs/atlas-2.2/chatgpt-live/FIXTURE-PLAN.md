# ChatGPT Live — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/chatgpt-live/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.
**DEMO ≠ RELEASE.**

## Family

| Family | Path | Package |
|---|---|---|
| chatgpt-live (base) | `docs/atlas-2.2/chatgpt-live/fixtures/` | AS-2.2-CHATGPT-LIVE-PREP-001 |
| chatgpt-live (deepen) | `docs/atlas-2.2/chatgpt-live/fixtures/` | AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001 |

## Scenarios — base (#194)

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

## Scenarios — deepen (AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001)

| ID | File | Intent |
|---|---|---|
| FX-2.2-CGL-101 | `negative-env-force-live.expect.json` | Env force-live → rejected |
| FX-2.2-CGL-102 | `negative-billing-without-opt-in.expect.json` | Billing without opt-in → rejected |
| FX-2.2-CGL-103 | `negative-bypass-quarantine-deepen.expect.json` | Quarantine bypass reaffirm → rejected |
| FX-2.2-CGL-104 | `negative-release-cert-stamp.expect.json` | Release-cert stamp → rejected |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data / API keys in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never mutate runtime `chatgpt_bridge` from fixture success
- Env alone ≠ live opt-in; billing/network spend requires explicit `opt_in`

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-CGL-001..008 | payload-present (docs sketch) | **NO** |
| FX-2.2-CGL-101..104 | payload-present (deepen docs sketch) | **NO** |

Promotion to harness + production schemas requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
