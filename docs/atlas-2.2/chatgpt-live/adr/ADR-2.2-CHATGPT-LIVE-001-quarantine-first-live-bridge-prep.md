# ADR-2.2-CHATGPT-LIVE-001 — Quarantine-first live ChatGPT bridge (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-CHATGPT-LIVE-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b5d8729` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

GAP-NS-007 calls for a live ChatGPT API bridge that is quarantine-first.
Today Atlas ships an export-only bridge (`AS-2.1-CHATGPT-BRIDGE-001`) with
`live_chatgpt_api=false`. Pre-unlock work must not mutate that runtime while
still landing reviewable contracts for the optional 2.2 live path.

## Decision

1. Land live-bridge architecture, JSON Schema stubs, and fixtures under
   `docs/atlas-2.2/chatgpt-live/**` only.
2. Treat `project_atlas.chatgpt_bridge` as **consume-only** until
   `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Require quarantine-first semantics: no bypass, no Layer B write, no LLM
   authority stamp, no default-on live client, no PILOT invent.
4. Do **not** mutate runtime `chatgpt_bridge` in this PREP PR.

## Consequences

- Positive: parallel-safe prep; clear fail-closed live wall; gap register
  package has an owned doc surface.
- Negative: no live network client until post-`v2.1.0` unlock; fixtures grant
  no gate credit.

## Non-decisions

- Exact ChatGPT/OpenAI transport client and auth storage
- Whether Mission/Workspace surfaces embed quarantine receipts vs deep-links
- Any change to export-bridge receipt schema enums
