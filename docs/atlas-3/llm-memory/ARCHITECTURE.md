# Atlas 3 — Universal LLM memory architecture

| Field | Value |
|---|---|
| Directive | D-192 |
| Status | **CANONICAL MEMORY PROGRAM ARCHITECTURE** |
| Truth boundary | `LLM OUTPUT != AUTHORITY` · `CONVERSATION != TRUTH CORE` |

## Intent

Evolve Atlas from project knowledge compiler + agent context provider into:

```text
UNIVERSAL CROSS-LLM PROJECT MEMORY
+
VERIFIABLE SHARED REALITY LAYER
```

Target loop:

```text
ChatGPT learns → Claude decides/discusses → Gemini researches
→ Cursor/Codex implements → Atlas captures → provenance + reconcile
→ next AI receives current reconciled context
```

## Do not rebuild

Already on main (compose, do not replace):

- `chatgpt_bridge.py` / `chatgpt_capture.py` (ChatGPT export + fixture receipt)
- `conversation_capture.py` + `atlas.conversation-capture.v1`
- Knowledge Inbox
- provider quarantine (`provider_adapters.py`)
- secrets, project identity, claims/conflicts/UNKNOWN
- authority + temporal/freshness
- Context Compiler / Ask2
- handoff/resume
- MCP read-only
- CLAUDE.md / GEMINI.md / AGENTS.md **bootstrap adapters** (≠ ingestion)

Honest limitation:

```text
TRANSCRIPT EXTRACTION / AUTOMATIC PROVIDER HISTORY SYNC
IS NOT A GENERAL CORE CAPABILITY.

ChatGPT export import = IMPLEMENTED
Claude / Gemini native full-account history sync = NOT IMPLEMENTED
```

## Target architecture

```text
ChatGPT / Claude / Gemini / Cursor / Codex / Copilot / future
        │
        ▼
PROVIDER CONNECTOR LAYER          (AT3-035)
        │
        ▼
RAW CONVERSATION EVIDENCE         (hash + refs; minimize raw transcript)
        │
        ▼
SECRET / PRIVACY / POLICY GATE    (AT3-047)
        │
        ▼
QUARANTINE                        (existing PROV + inbox)
        │
        ▼
CONVERSATION NORMALIZER           (AT3-039)
        │
        ▼
KNOWLEDGE EXTRACTOR               (AT3-040, existing ITEM_TYPES)
        │
        ▼
KNOWLEDGE INBOX                   (existing)
        │
        ▼
RECONCILIATION                    (AT3-041/042/044/049)
        │
        ▼
MEMORY / INTENT PROJECTIONS       (derived; not Truth Core)
        │
        ▼
ATLAS CONTEXT COMPILER            (consume-only, ranked)
        │
        ▼
next LLM
```

## Reuse map

```text
REUSED_COMPONENTS =
  conversation_capture ITEM_TYPES + owner_origin fail-closed
  knowledge_inbox (no promote_authority)
  chatgpt_bridge + parse_chat_export (ChatGPT export)
  provider quarantine digest-only envelopes
  secrets.scan_text
  project routing / identity locks
  bitemporal primitives
  runtime_22 / context compiler (later consume-only)

NEW_COMPONENTS =
  atlas3.memory connector / envelope / normalize / extract / dedup /
  conflicts / freshness / search / reconcile / privacy / provider matrix

MIGRATION_REQUIRED = NO for Core capture schema
COMPATIBILITY_RISK = HIGH if chatgpt_bridge or conversation_capture contracts fork
```

## Context compiler ranking

1. Authoritative / current project evidence
2. Verified / derived Atlas truth
3. Accepted decisions
4. Current reconciled memory
5. Contested memory with explicit warning
6. UNKNOWN / open questions
7. Stale memory only when historical context is requested

Never rank recent LLM text above stronger project evidence merely because it
is newer.
