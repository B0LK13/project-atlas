# Evidence — AS-CODER-ALPHA-INCREMENTAL-CONNECT-001

DIRECTIVE: D-132 overnight Worker B
PACKAGE: `AS-CODER-ALPHA-INCREMENTAL-CONNECT-001`
BRANCH: `cursor/atlas-autonomous-night-cycle-742c` (IV re-base)
EXACT_MAIN: `4e71cce0d1c97f408347e256300a41590da4c352`

```
INCREMENTAL_SKIP != TRUTH_CORE_AUTHORITY
PREP != IMPLEMENTED
DEMO != RELEASE
MODEL OUTPUT != AUTHORITY
INDEPENDENT_IV = PASS_ON_CURRENT_MAIN
IV_COMMAND = pytest tests/unit/test_as_coder_alpha_incremental_connect_001.py --no-cov
IV_RESULT = 14 passed
```

## Change

`connect_project()` inspects via discover, then skips redundant ingest and
derived rematerialization when the committed connect-manifest + complete
connect-receipt prove an unchanged active-source set.

Derived ops receipt: `generated/ops/incremental-connect-receipt.json`.

## Acceptance targets (test-enforced, not self-certified IV)

- `NO_CHANGE_DOUBLE_INGEST = 0`
- `SOURCE_DUPLICATION = 0`
- `FALSE_CHANGED_ITEMS = 0`
- `TRUTH_DRIFT = 0`
- `CROSS_PROJECT_LEAK_COUNT = 0`

## Surfaces not touched

`cli.py`, `mcp_server.py`, `mcp_registry.py`, `obsidian_projection.py`,
`apps/web/**`, `api_server.py`, `app_service.py`, `WORKLOG.md`, `docs/backlog.md`.
