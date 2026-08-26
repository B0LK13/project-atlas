# AS-CODER-ALPHA-CAPTURE-READ-001

Vault-scoped REPORT READ of existing session-capture receipts
(`generated/ops/session-captures/capture-*.json`).

- Surfaces: `atlas capture report|show`, `GET /v1/capture/report`, MCP `atlas.capture.read`
- Honesty: CAPTURE != AUTHORITY; SESSION != TRUTH; CONVERSATION != TRUTH
- Existing `atlas capture record|list` are unchanged
- Never calls `capture_session` / `list_captures`
- MERGE_AUTHORIZATION = NOT_GRANTED
