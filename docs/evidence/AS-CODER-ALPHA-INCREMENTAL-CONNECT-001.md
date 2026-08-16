# Evidence — AS-CODER-ALPHA-INCREMENTAL-CONNECT-001

DIRECTIVE: D-132 overnight Worker B
PACKAGE: `AS-CODER-ALPHA-INCREMENTAL-CONNECT-001`
BRANCH: `cursor/incremental-connect-001-315e`
EXACT_MAIN: `32c992894d7cabe58dd4b965585093fe6d308458`

```
INCREMENTAL_SKIP != TRUTH_CORE_AUTHORITY
PREP != IMPLEMENTED
DEMO != RELEASE
MODEL OUTPUT != AUTHORITY
INDEPENDENT_IV = PENDING
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
