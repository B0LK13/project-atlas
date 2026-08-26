# AS-CODER-ALPHA-HANDOFF-READ-001

Vault-scoped REPORT READ over persisted handoff packs.

- Function: `read_handoff_view` / `show_handoff_view`
- CLI: `atlas handoff-status report|show --vault <vault>`
- API: `GET /v1/handoff/report`
- MCP: `atlas.handoff.read`
- Reads `generated/ops/handoffs/` only
- Never calls `create_handoff` or `resume_handoff`
- EMPTY != HEALTHY; UNKNOWN != HEALTHY
- HANDOFF REPORT != AUTHORITY
- MERGE_AUTHORIZATION = NOT_GRANTED
