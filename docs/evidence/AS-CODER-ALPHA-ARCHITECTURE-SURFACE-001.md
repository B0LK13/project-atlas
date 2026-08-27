# AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001

```
PACKAGE = AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001
LEASE_ID = LEASE-IMPL-ARCH-SURF-053-A
DIRECTIVE = D-053
BRANCH = feat/as-coder-alpha-architecture-surface-001
EXACT_BASE = dc9d81df0ff7106438de44a4bd84df0b955535bc
DRAFT = YES
CERTIFICATION = NOT_GRANTED
MERGE_AUTHORIZATION = NOT_GRANTED
INDEPENDENT_IV = PENDING
SELF_REVIEW != INDEPENDENT_IV
```

Read-only LIVE_API projection of the existing `build_architecture_lens`
(AS-CODER-ALPHA-ARCH-002). Does not materialize `generated/answers/`, does not
edit `cli.py`, and does not rebase or twin #404 stale-wiring.

```
GET /v1/architecture?project=<id>
MISSING_PROJECT = FAIL_CLOSED
EMPTY_PROJECT = FAIL_CLOSED
NO_IMPLICIT_PORTFOLIO_ALL = YES
POST/PUT/DELETE = 405 writes-forbidden
LENS_IS_AUTHORITY = false
UI_IS_CANONICAL = false
UNKNOWN_EMPTY_STAYS_UNKNOWN = YES
DO_NOT_INVENT_STACK = YES
CROSS_PROJECT_LEAK_COUNT = 0
SECRET_ECHO = NO
LAYER_B_WRITE = NO
```

## Surfaces

Allowed:

- `src/project_atlas/web_api/architecture.py` (new)
- `src/project_atlas/api_server.py` (route register + `architecture_live` meta)
- `src/project_atlas/app_service.py` (thin `architecture()` wiring)
- `tests/unit/test_as_coder_alpha_architecture_surface_001.py` (new)
- `docs/evidence/AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001.md` (this file)

Forbidden / not touched: `cli.py`, `project_architecture.py`, lens files from
#414, `project_brief.py`, `project_changed.py`, `agent_handoff.py`,
`apps/web/**`, architecture-stale wiring.

## Honesty

ARCHITECTURE LENS != AUTHORITY. UI != CANONICAL. UNKNOWN != STACK.
API != TRUTH CORE. MODEL OUTPUT != AUTHORITY.
