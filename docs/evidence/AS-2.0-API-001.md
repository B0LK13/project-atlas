# AS-2.0-API-001 — Read-only Intelligence API

Implemented from Wave-6 contracts after D-120 unlock and stack refresh.

GET only:

- `/v1/intelligence/evidence`
- `/v1/intelligence/conflicts`
- `/v1/intelligence/explain`
- `/v1/project-state`
- `/v1/project-attention`
- `/v1/portfolio-state`

Does not replace `/v1/conflicts`.
No POST. No canonical writes. No new auth scope.

`DERIVED_INTELLIGENCE_IS_AUTHORITY = NO`
`CANONICAL_WRITE = NO`
