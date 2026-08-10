# ChatGPT Live — hard invariants (PREP)

Package: **AS-2.2-CHATGPT-LIVE-PREP-001**  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. Quarantine-first

| Signal | Allowed | Forbidden |
|---|---|---|
| Live payload accepted | Write via `quarantine_provider_output` | Skip / inline Layer B write |
| Quarantine status | `quarantined` / `rejected-secret` / `rejected-disabled` | Invent `promoted` |
| Missing quarantine ref | reject receipt | Forge envelope id |

Any consumer that routes live ChatGPT text around quarantine is
**out of contract**.

## 2. LLM ≠ authority

| Field | Const / rule |
|---|---|
| `authority.level` on envelopes | `derived` |
| `llm_authority` | `false` |
| Subjective confidence / trust | **forbidden** (objective signals only) |
| Layer B / claims write from live turn | **forbidden** |

Truth boundary string (prep):  
`CHATGPT LIVE ≠ BYPASS QUARANTINE / ≠ LAYER B / ≠ AUTHORITY / LLM≠AUTHORITY`

## 3. Live default off / export remains default

| Signal | Allowed | Forbidden |
|---|---|---|
| Export bridge path | Continue as default | Relabel export as live API |
| Live request | Explicit `opt_in=true` only | Default-on live client |
| `live_chatgpt_api` on export receipts | remains `false` | Flip without unlock |

## 4. No runtime `chatgpt_bridge` mutation in PREP

This PREP lane **must not** edit:

- `src/project_atlas/chatgpt_bridge.py`
- `src/project_atlas/chatgpt_capture.py`
- shipped package schemas for chatgpt capture/bridge
- provider adapter quarantine defaults

Consume-only references to AS-2.1-CHATGPT-BRIDGE-001 helpers are documentation
links, not code ownership.

## 5. UI ≠ canonical

| Surface | May do | Must not do |
|---|---|---|
| Live session panel | Render quarantine receipt | Write Layer B / claims |
| Operator action | escalate / open evidence | `_promote` / canonical write |
| Ask Atlas citation | Cite quarantine envelope id | Stamp authority |

## 6. Env / billing fail-closed (no live OAI verification)

| Signal | Allowed | Forbidden |
|---|---|---|
| Missing `OPENAI_API_KEY` (name only in fixtures) | `rejected_forbidden` / `rejected-disabled` | Proceed with live network call |
| Billing / spending-limit gate | Block before API call | Charge live OpenAI billing in PREP |
| Env var values in fixtures | Env **names** only | Embed API keys / secrets / tokens |

PREP fixtures rehearse fail-closed gates only. They do **not** verify live OpenAI
billing, quota, or credential validity.

## 7. no PILOT invent / certification wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture live-session rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock. **Never PILOT.**
