# ChatGPT Live — hard invariants (PREP)

Packages: **AS-2.2-CHATGPT-LIVE-PREP-001** (base) ·
**AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001** (deepen)  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. Quarantine-first

| Signal | Allowed | Forbidden |
|---|---|---|
| Live payload accepted | Write via `quarantine_provider_output` | Skip / inline Layer B write |
| Quarantine status | `quarantined` / `rejected-secret` / `rejected-disabled` | Invent `promoted` |
| Missing quarantine ref | reject receipt | Forge envelope id |

Any consumer that routes live ChatGPT text around quarantine is
**out of contract**. Deepen reaffirmation: `bypass_quarantine` remains
`rejected_forbidden` (FX-2.2-CGL-103).

## 2. ENV ≠ OPT-IN (deepen)

| Signal | Allowed | Forbidden |
|---|---|---|
| Live enablement | Explicit operator `opt_in=true` | `OPENAI_API_KEY` / `ATLAS_LIVE_*` alone forcing live |
| Env presence | Credential source after opt-in | Silent `live_chatgpt_api=true` via env |

Truth boundary (deepen): `ENV ≠ OPT-IN`.

## 3. BILLING ≠ SILENT (deepen)

| Signal | Allowed | Forbidden |
|---|---|---|
| Paid live API call | After explicit `opt_in=true` | Network/billing spend without opt-in |
| Meter / cost signals | Objective counters post-unlock | Silent unmetered spend from PREP fixtures |

Truth boundary (deepen): `BILLING ≠ SILENT`.

## 4. LLM ≠ authority

| Field | Const / rule |
|---|---|
| `authority.level` on envelopes | `derived` |
| `llm_authority` | `false` |
| Subjective confidence / trust | **forbidden** (objective signals only) |
| Layer B / claims write from live turn | **forbidden** |

Truth boundary string (prep):  
`CHATGPT LIVE ≠ BYPASS QUARANTINE / ≠ LAYER B / ≠ AUTHORITY / LLM≠AUTHORITY`

## 5. Live default off / export remains default

| Signal | Allowed | Forbidden |
|---|---|---|
| Export bridge path | Continue as default | Relabel export as live API |
| Live request | Explicit `opt_in=true` only | Default-on live client |
| `live_chatgpt_api` on export receipts | remains `false` | Flip without unlock |

## 6. No runtime `chatgpt_bridge` mutation in PREP

This PREP lane **must not** edit:

- `src/project_atlas/chatgpt_bridge.py`
- `src/project_atlas/chatgpt_capture.py`
- shipped package schemas for chatgpt capture/bridge
- provider adapter quarantine defaults
- `docs/atlas-2.2/ask-atlas-2/**` (Ask Atlas 2 deepen peer)

Consume-only references to AS-2.1-CHATGPT-BRIDGE-001 helpers are documentation
links, not code ownership.

## 7. UI ≠ canonical

| Surface | May do | Must not do |
|---|---|---|
| Live session panel | Render quarantine receipt | Write Layer B / claims |
| Operator action | escalate / open evidence | `_promote` / canonical write |
| Ask Atlas citation | Cite quarantine envelope id | Stamp authority |

## 8. no PILOT invent / certification wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture live-session rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock. **Never PILOT.** **DEMO ≠ RELEASE.**
