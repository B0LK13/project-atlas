# AS-2.0-API-001 — Read-only Intelligence API

Directive: `D-PROJECT-ATLAS-CLOUD-AUTONOMOUS-2.0-D121-INTEGRATION-READINESS-WAVE15-WAVE16`

Implemented from Wave-6 contracts on the D-121 integration head.

```
GET_ONLY = YES
POST_ENDPOINTS = 0
CANONICAL_WRITES = 0
NEW_WRITE_SCOPE = NO
NEW_AUTH_SCOPE = NO
API_RESULT_IS_AUTHORITY = NO
REPLACES_V1_CONFLICTS = NO
```

## Surfaces

Dedicated GET routes (Wave-6 contract):

- `GET /v1/intelligence/evidence`
- `GET /v1/intelligence/conflicts` — does **not** replace `GET /v1/conflicts`
- `GET /v1/intelligence/explain`
- `GET /v1/project-state`
- `GET /v1/project-attention`
- `GET /v1/portfolio-state`

Certified library query kinds (no duplicate dedicated semantics):

- `GET /v1/intelligence/query?kind=change`
- `GET /v1/intelligence/query?kind=context`
- `GET /v1/intelligence/query?kind=gap-priority`
- `GET /v1/intelligence/query?kind=dependencies`
- `GET /v1/intelligence/query?kind=decision`

Dedicated kinds (`evidence`, `conflicts`, `explain`, `state`, `attention`)
are rejected on `/v1/intelligence/query` as `UNSUPPORTED_SCOPE`.

## Honesty classes

`UNKNOWN` / `NO_DATA` / `VALID_EMPTY` / `NO_MATCH` / `CONTESTED` / `STALE` /
`HTTP_FAILURE` / `MALFORMED_INPUT` / `UNSUPPORTED_SCOPE`

Never:

- HTTP_FAILURE → demo
- UNKNOWN → false
- NO_DATA → healthy
- CONTESTED → resolved
- STALE → invalid

## Auth / write

Existing LIVE_API `api.read` Bearer only. No new auth capability.
POST to intelligence routes remains `405 writes-forbidden`.
Existing POST surface is unchanged (`/v1/actions`, `/v1/captures/conversation`).
