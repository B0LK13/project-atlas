# AS-CODER-ALPHA-DECISIONS-API-001 — read-only GET /v1/decisions

Package ID: `AS-CODER-ALPHA-DECISIONS-API-001`.

Projects `atlas decisions` / `build_decisions_lens` to LIVE_API. Does not write
Layer B. Does not treat `ACTIVE_GOVERNING` as a trust score or owner grant.

Honesty:

- `DECISIONS != AUTHORITY`
- `ACTIVE_GOVERNING != TRUST SCORE`
- `UNKNOWN != HEALTHY`
- `NO IMPLICIT PORTFOLIO-ALL`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Web companion: `AS-CODER-ALPHA-DECISIONS-WEB-001` (`#/decisions`).
