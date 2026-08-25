# AS-CODER-ALPHA-CAPTURE-LIST-001 — Session-capture list

Read-only inventory of Coder Alpha session-memory receipts.

Package ID: `AS-CODER-ALPHA-CAPTURE-LIST-001`.

## What this is

`atlas capture record` already writes ops receipts under
`generated/ops/session-captures/`. This package exposes that inventory on the
read surfaces that agents and operators already use:

| Surface | Contract |
|---|---|
| Library | `read_vault_session_captures()` |
| LIVE_API | `GET /v1/captures` (optional `?project=` / `?limit=`) |
| MCP | zero-arg `atlas.captures.list.read` |
| Web | `#/captures` (UI ≠ canonical) |

## Honesty

- Session captures are **ops receipts**, not Layer B / Truth Core.
- Empty vaults return an empty list; UNKNOWN stays UNKNOWN.
- MCP is vault-scoped and zero-arg. Project filters are LIVE_API/Web only.
- Conversation captures (`ccap-*.json`) are a different quarantine surface and
  are not mixed into this list.
- `OWNER_CAPABILITY_GRANTED` is not derived from capture presence.
- `AUTHENTIC_PILOT` remains false on this lens.

## Out of scope

- Writing or promoting captures to canonical notes
- Authentic O2 / estate credential consumption
- Conversation-capture POST (`/v1/captures/conversation`)
- Merge authorization
