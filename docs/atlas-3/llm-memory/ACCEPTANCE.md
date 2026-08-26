# Atlas 3 — LLM memory acceptance

## Success criterion (D-192 §34)

Not complete when a provider can upload a transcript.

Complete when:

1. Multiple providers can contribute project knowledge
2. Duplicates are reconciled
3. Contradictions are preserved
4. Stale knowledge is invalidated
5. Provenance is intact
6. Owner decisions cannot be forged
7. Secrets do not leak
8. Stronger project evidence outranks LLM memory
9. Context Compiler can serve reconciled memory to another provider
10. A user can move ChatGPT → Claude → Gemini → Cursor/Codex without
    re-explaining project history

## This slice (honest)

| Criterion | This slice |
|---|---|
| 1 | Fixture-level ChatGPT + Claude + Gemini envelopes |
| 2–8 | Isolated runtime + tests |
| 9 | AT3-054 rank + AT3-055 local pack serve; live serve EXTERNAL_BLOCKED; no Ask2 rewrite |
| 10 | AT3-056 fixture ChatGPT→Claude handoff; live multi-account product EXTERNAL_BLOCKED |

Claude/Gemini **native history sync** remains **NOT IMPLEMENTED**.
Cursor **Cloud history sync** remains **NOT IMPLEMENTED** (AT3-057 is local-session fixture ingest only).
Codex **native history sync** remains **NOT IMPLEMENTED** (AT3-058 is structured-submission fixture ingest only).

## PostgreSQL multi-provider fixture

See `tests/fixtures/atlas3/llm-memory/postgres-cross-llm.json`.

Required outputs:

```text
CURRENT = PostgreSQL 15
INTENT = PostgreSQL 16 later
CONFLICTED_HISTORY = YES
STALE_CHATGPT_MEMORY = YES
OWNER_DECISION = supported only by explicit owner evidence
NEXT CONTEXT ≠ "current production is PostgreSQL 16"
PROMOTED_TO_TRUTH_CORE = 0
```
