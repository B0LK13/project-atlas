# AS-CODER-ALPHA-CONVERSATION-CAPTURE-MCP-001 — conversation inventory

Package ID: `AS-CODER-ALPHA-CONVERSATION-CAPTURE-MCP-001`.

Read-only inventory of quarantined `atlas.conversation-capture.v1` receipts.
Does not submit, review, or promote to Truth Core.

## Surfaces

- MCP: zero-arg `atlas.conversation.read`
- LIVE_API: `GET /v1/conversation-captures` (optional `?project=`)
- Web: `#/conversation-captures`
- CLI: `atlas capture conversations`

## Honesty

- `CAPTURE != TRUTH CORE`
- `CONVERSATION != AUTHORITY`
- `MCP != WRITE`
- `UI != CANONICAL`
- Empty inventory is UNKNOWN, not a healthy zero
- `AUTHENTIC_PILOT = NO`

## Non-goals

- D-149 owner-gate remediation (remains draft `#483`)
- Authentic O2
- Merge authorization
