# ADR-2.2-CHATGPT-LIVE-001 — Quarantine-first live ChatGPT bridge deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `103ca52` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 chatgpt-live PREP (PR #194) landed quarantine-first architecture, schema
stubs, and base negative fixtures under `docs/atlas-2.2/chatgpt-live/`. Sibling
wave-2/3 deepen packages (reality-live, mem-gov, time-machine, Ask Atlas 2)
carry explicit deepen package cards and peer-depth forbidden vocabulary.
ChatGPT live lacked a `*DEEPEN-PREP-001*` card and was missing env / billing /
release-cert fail-closed rehearsal depth.

Productionization posture reinforces that **DEMO VERIFIED ≠ release
certification** — fixture rehearsal must not stamp
`ATLAS_2_1_RELEASE_CERTIFIED`.

## Decision

1. Land deepen package card, deepen ADR, deepen forbidden-action schema, and
   negative fixtures under `docs/atlas-2.2/chatgpt-live/**` only.
2. Keep base request / quarantine / receipt stubs and FX-001..008 at their
   existing paths — no relocation or dual ownership.
3. Extend fail-closed vocabulary to peer depth covering **env** force-live,
   **billing** without opt-in, **quarantine** bypass reaffirmation, and
   release-cert stamps.
4. Do **not** dual-own `ask-atlas-2/**` or mutate `chatgpt_bridge` /
   `chatgpt_capture` until unlock.

## Consequences

- Positive: chatgpt-live reaches sibling deepen artifact depth; clear
  fail-closed vocabulary for future live-bridge implementers.
- Negative: no live network client until post-`v2.1.0` unlock; fixtures grant
  no gate credit. Demo ≠ release.

## Non-decisions

- Exact ChatGPT/OpenAI transport client and auth / billing meter storage
- Whether Mission/Workspace surfaces embed quarantine receipts vs deep-links
- Any change to export-bridge receipt schema enums
