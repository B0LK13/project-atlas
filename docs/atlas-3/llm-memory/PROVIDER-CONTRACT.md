# Atlas 3 — Provider adapter contract

Every provider adapter emits the same canonical envelope.
Raw provider schemas must not leak into Truth Core.

## Canonical envelope fields

| Field | Required | Notes |
|---|---|---|
| `provider` | yes | `chatgpt`, `claude`, `gemini`, `cursor`, `codex`, `copilot`, … |
| `provider_account_scope` | no | Opaque; never a secret |
| `conversation_id` | yes | Provider conversation id or derived stable id |
| `message_id` | yes | Per-message |
| `parent_message_id` | no | Threading |
| `thread_id` | no | |
| `project_id` | yes at route time | Fail closed if ambiguous |
| `source_timestamp` | no | Provider-declared |
| `retrieved_at` | observation | Import/observation time — not valid-time authority |
| `role` | yes | `user` / `assistant` / `system` / `tool` / `owner` |
| `content_hash` | yes | `sha256:…` of normalized text |
| `content_reference` | yes | Pointer or redacted excerpt, not unnecessary full dump |
| `attachment_refs` | no | Must pass source safety |
| `model_name` | no | Informational |
| `tool_refs` | no | |
| `source_url_or_external_id` | no | |
| `import_mode` | yes | See modes |
| `sync_cursor` | no | Incremental |
| `provider_metadata` | no | Quarantined sidecar; not Layer B |
| `privacy_class` | yes | `include` / `exclude` / `redact` / `quarantine` |
| `retention_class` | yes | Default minimize raw transcript |

## Import modes

```text
IMPORT_MODE =
  EXPORT | API | LOCAL_SESSION | PLUGIN | MCP | MANUAL | STRUCTURED_SUBMISSION
```

Never invent unsupported provider APIs.
Do not scrape authenticated UIs as a silent default.

If history cannot be fetched programmatically:

```text
CAPABILITY = EXPORT_ONLY | MANUAL_CAPTURE
```

## Provider states (honest)

`CONNECTED` · `AVAILABLE` · `EXPORT_ONLY` · `PARTIAL` · `AUTH_REQUIRED` ·
`PERMISSION_DENIED` · `RATE_LIMITED` · `UNSUPPORTED` · `EXTERNAL_BLOCKED` ·
`ERROR`

Do not call a provider synchronized when only local fixture coverage exists.

## Adapter rule

```text
PROVIDER FORMAT → CANONICAL CONVERSATION FORMAT
Core / Truth consumes only canonical format (and existing capture schema).
```

ChatGPT adapter **wraps** `parse_chat_export` / export bridge outputs.
It does not replace `chatgpt_bridge.py`.
