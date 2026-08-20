# Evidence — AS-CODER-ALPHA-NEXT-API-001

LEASE: `CLOUD-031-E-NEXT-API`
DIRECTIVE: `D-CLOUD-PARALLEL-DAG-EXECUTION-031`
PACKAGE: `AS-CODER-ALPHA-NEXT-API-001`
BRANCH: `cursor/next-api-001-5d32`
BASE: `5b7f564863d09d82fb7977cfc495f5a2b5124f6b`

## Honesty

- `NEXT LENS != AUTHORITY`
- `NEXT ACTION != COMMAND`
- `API != TRUTH CORE`
- `UNKNOWN` is valid
- No Layer B writes
- Does not materialize `generated/answers/`
- Does not mutate historical #390
- `MERGE_AUTHORIZATION = NOT_GRANTED`
- `INDEPENDENT_IV = PENDING`
- `CERTIFICATION = NOT_GRANTED`

## Scope

Read-only `GET /v1/next?project=<id>` plus AppService `next_lens`.
Project token required. Cross-project values must not leak.
