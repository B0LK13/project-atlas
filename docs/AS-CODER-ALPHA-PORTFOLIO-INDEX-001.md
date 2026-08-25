# AS-CODER-ALPHA-PORTFOLIO-INDEX-001 — vault-scoped portfolio index

Package ID: `AS-CODER-ALPHA-PORTFOLIO-INDEX-001`.

Read-only Web `#/portfolio` and zero-arg MCP `atlas.portfolio.state.read`
over existing LIVE_API surfaces:

- project inventory via `/v1/projects` (Web: read-status / `/v1/snapshot`)
- `/v1/portfolio-state?project=<id>&project=<id>` with those explicit ids

## What this is not

- not a new `/v1/portfolio` protocol
- not an empty-arg `/v1/portfolio-state` call (`UNSUPPORTED_SCOPE` remains)
- not portfolio authority (`PORTFOLIO != AUTHORITY`)
- not UI canonical truth (`UI != CANONICAL`)
- not owner capability (`OWNER_CAPABILITY_GRANTED = false`)
- not authentic O2 / D-149

Demo stub lists inventory rows when present but never fabricates a
portfolio body.

## Honesty

- `zero_arg_vault_scope = true`
- `portfolio_implicit_all = false`
- `empty_arg_portfolio_state = false`
- `mcp_is_authority = false`
- `authentic_pilot = false`

## Validation

```bash
.venv/bin/python -m pytest \
  tests/unit/test_as_coder_alpha_portfolio_index_web_001.py \
  tests/unit/test_as_coder_alpha_portfolio_index_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py \
  -q --no-cov
```
