# Live ChatGPT API bridge — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Provide an **optional, quarantine-first live ChatGPT API bridge** that can pull
conversation turns from an external ChatGPT-compatible API into Atlas
provider/PROV quarantine — without mutating the certified export bridge
(`chatgpt_bridge`), without default-on network clients, and without granting
LLM text Layer B authority.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Operator / Ask / MCP lenses — consume quarantine receipts  │
│  UI ≠ canonical · Live ≠ Layer B · LLM ≠ authority          │
├─────────────────────────────────────────────────────────────┤
│  2.2 Live bridge service (future AS-2.2-CHATGPT-LIVE-001)   │
│    request(opt_in) → LiveBridgeRequest                      │
│    fetch → QuarantineEnvelope (mandatory)                   │
│    receipt → LiveSessionReceipt (derived)                   │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on main — consume only / conceptual)    │
│    AS-2.1-CHATGPT-BRIDGE-001 export → quarantine            │
│    AS-2.0-CHATGPT-CAPTURE-001 fixture capture               │
│    provider_adapters.quarantine_provider_output             │
│    generated/ops/chatgpt/* receipts (export path today)     │
├─────────────────────────────────────────────────────────────┤
│  Adjacent (do not dual-own)                                 │
│    AS-2.0-OAI-IMPORT / Responses POC quarantine             │
│    AS-2.2-RESEARCH-001 / Ask Atlas 2 (cite receipts only)   │
└─────────────────────────────────────────────────────────────┘
```

## Quarantine-first flow (conceptual)

```text
opt-in live request
        │
        v
  secret scan + adapter gate
        │
        +-- rejected-disabled / rejected-secret / rejected_forbidden
        │
        v
  quarantine_provider_output(...)   ← mandatory; never skip
        │
        v
  LiveSessionReceipt (derived)
        │
        +-- live_chatgpt_api=true (session flag only)
        +-- llm_authority=false
        +-- canonical_write=false
        +-- layer_b_write=false
```

## Substrate mapping

| Bucket | Source package | Emit path (frozen on main) | Prep rule |
|---|---|---|---|
| Export bridge receipt | AS-2.1-CHATGPT-BRIDGE-001 | `generated/ops/chatgpt/{id}-bridge.json` | Consume-only; do not mutate |
| Capture receipt | AS-2.0-CHATGPT-CAPTURE-001 | `generated/ops/chatgpt/{id}.json` | `live_api` remains forbidden |
| Provider quarantine | provider adapters | quarantine envelopes under vault | Mandatory for live payloads |
| Live session (future) | AS-2.2-CHATGPT-LIVE-001 | TBD post-unlock | Opt-in; quarantine-first |

## Live session receipt (conceptual)

A session result is a **derived, deterministic** envelope:

- `session_id` — stable rehearsal id
- `live_chatgpt_api` — true only when opt-in path exercised
- `quarantine` — envelope id + status (`quarantined` / reject codes)
- `turn_count` — objective count only
- `authority.level = derived`
- `llm_authority = false`
- `canonical_write = false`
- `bypass_quarantine = false`
- `atlas_2_1_release_certified = false` on all prep fixtures
- `pilot_roots = 0`

## Deepen delta (AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001)

Base PREP (#194) covered quarantine-first stubs and base negatives. Deepen adds
peer-depth fail-closed vocabulary:

| Theme | Forbidden kind | Fixture |
|---|---|---|
| Env | `env_force_live` | FX-2.2-CGL-101 |
| Billing | `billing_without_opt_in` | FX-2.2-CGL-102 |
| Quarantine | `bypass_quarantine` (reaffirm) | FX-2.2-CGL-103 |
| Release cert | `release_cert_stamp` | FX-2.2-CGL-104 |

Ask Atlas 2 deepen (`ask-atlas-2/**`) remains a **peer** — cite quarantine
receipts only; do not dual-own answer-lens contracts.

## Non-goals

- Mutating `project_atlas.chatgpt_bridge` or flipping export defaults
- Default-on live network clients or credential stores in Core
- Env-forced live enablement or silent billing/network spend
- Promoting quarantined LLM text to Layer B / claims
- Subjective trust / confidence scores
- Authentic estate PILOT evidence from fixtures
- Stamping `ATLAS_2_1_RELEASE_CERTIFIED` from fixture rehearsal (DEMO ≠ RELEASE)
- Dual-owning `docs/atlas-2.2/ask-atlas-2/**`

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Quarantine-first: live prep never calls `_promote` / never mutates Layer B
- Live opt-in remains explicit; disabled/default path stays export-only
- Env presence ≠ opt-in; billing requires explicit operator consent
