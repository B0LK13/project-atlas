# Atlas 3 — Provider capability matrix

Honesty: local fixture coverage ≠ synchronized provider.

| Provider | Structured capture | Export import | Live full history | Bootstrap adapter | Atlas 3 state |
|---|---|---|---|---|---|
| ChatGPT | Yes (`chatgpt`) | **Implemented** (`chatgpt_bridge`, `oai-import`, `parse_chat_export`) | **Not generalized** (chatgpt-live PREP; `live_api=false`) | MCP read demo | `EXPORT_ONLY` + structured |
| Claude | Yes (`claude`) | **Implemented** (isolated fixture/export ingest; not a 2.x Core bridge) | Not implemented; do not invent APIs | `CLAUDE.md` ≠ ingestion | `EXPORT_ONLY` / `MANUAL_CAPTURE` |
| Gemini | Opaque token `gemini` | **Implemented** (isolated fixture/export ingest; not a 2.x Core bridge) | Not implemented; do not invent APIs | `GEMINI.md` ≠ ingestion | `EXPORT_ONLY` / `MANUAL_CAPTURE` |
| Cursor | Yes (`cursor`) | **Implemented** (isolated local-session JSON fixture; not a 2.x Core bridge) | Not implemented; do not invent Cursor Cloud APIs | `AGENTS.md` / Cursor rules ≠ ingestion | `LOCAL_SESSION` / `STRUCTURED_SUBMISSION` |
| Codex | Yes (`codex`) | **Implemented** (isolated structured-submission JSON fixture; not a 2.x Core bridge) | Not implemented; do not invent native history APIs | `CODEX.md` ≠ ingestion | `STRUCTURED_SUBMISSION` / `LOCAL_SESSION` |
| Copilot | Future token | Unsupported | Unsupported | None | `UNSUPPORTED` |
| Generic SDK | AT3-035 registry | Adapter-defined | Adapter-defined | N/A | Fail closed if undeclared |

## Priority

1. ChatGPT (strongest substrate)
2. Claude
3. Gemini
4. Cursor
5. Codex
6. Generic provider SDK

## Commands (design before proliferation)

Target:

```text
atlas provider register
atlas provider capabilities
atlas provider sync
```

This slice exposes `atlas memory providers` as a read of the matrix.
It does not invent live sync.
