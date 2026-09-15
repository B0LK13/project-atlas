# Atlas 3 — Conversation normalization

AT3-039 maps any supported provider payload to the canonical envelope.

## Rules

1. Unicode NFC, strip, deterministic field order.
2. Role mapping is explicit (`Human`→`user`, `AI`→`assistant`).
3. Content is hashed; raw full transcript retention defaults to minimized.
4. Provider-specific keys stay in `provider_metadata` (sidecar).
5. Missing project identity is not guessed.
6. Timestamps are recorded as observations; they do not invent valid-time.
7. Oversized payloads fail closed.
8. Secret-shaped content fails closed or redacts per privacy policy — never
   persisted as a secret echo.

## ChatGPT

Reuse `project_atlas.openai_importer_fixtures.parse_chat_export` for
User/Assistant (Human/AI) turns. JSON export objects, when present, map
conversation id + message id from the file. Live API is **not** enabled.

## Claude / Gemini

This slice accepts:

- structured submission (already Core)
- fixture / export-like turn text through the same turn parser when the
  file is a generic User/Assistant transcript
- capability honesty: `EXPORT_ONLY` or `MANUAL_CAPTURE`

CLAUDE.md / GEMINI.md bootstrap support is **not** conversation ingestion.

## Idempotency

`content_hash` + `provider` + `conversation_id` + `message_id` define replay.
Same input → same envelope id.
