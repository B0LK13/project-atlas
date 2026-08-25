# AS-CODER-ALPHA-REVIEW-MCP-001 — vault-scoped review read

Package ID: `AS-CODER-ALPHA-REVIEW-MCP-001`.

Read-only inventory of `review/pending` and recorded `state/human-decisions`.
Does not accept, reject, or promote reviews.

## Surfaces

- MCP: zero-arg `atlas.review.read`
- LIVE_API: `GET /v1/reviews` (optional `?project=`)
- Web: `#/reviews` (optional `?project=`)

## Honesty

- `REVIEW READ != AUTHORITY`
- `MCP != DECIDE`
- `UI != CANONICAL`
- Empty inventory is UNKNOWN, not a healthy zero
- `AUTHENTIC_PILOT = NO`
- D-149 remains owner-held on draft `#483`
