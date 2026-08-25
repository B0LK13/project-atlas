# AS-CODER-ALPHA-OVERVIEW-API-001 — read-only GET /v1/overview

Package ID: `AS-CODER-ALPHA-OVERVIEW-API-001`.

Projects the existing `atlas overview` / `build_overview_lens` lens to LIVE_API.
Does not invent a second overview engine. Does not call
`materialize_overview_lenses` (no `generated/answers` writes).

Honesty:

- `OVERVIEW != AUTHORITY`
- `UNKNOWN != HEALTHY`
- `API != TRUTH CORE`
- `UI != CANONICAL`
- `NO IMPLICIT PORTFOLIO-ALL`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

Web companion: `AS-CODER-ALPHA-OVERVIEW-WEB-001` (`#/overview`).
