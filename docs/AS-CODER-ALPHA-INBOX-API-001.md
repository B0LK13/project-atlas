# AS-CODER-ALPHA-INBOX-API-001 — read-only GET /v1/inbox

Package ID: `AS-CODER-ALPHA-INBOX-API-001`.

Projects the existing `atlas inbox list` / `list_inbox_items` lens to LIVE_API.
Does not invent a second inbox engine. Does not mutate inbox items, promote
authority, or execute commands.

Honesty:

- `INBOX != AUTHORITY`
- `LISTING != MUTATION != COMMAND`
- `API != TRUTH CORE`
- `UI != CANONICAL`
- `NO IMPLICIT PORTFOLIO-ALL`
- `MERGE_AUTHORIZATION = NOT_GRANTED`
