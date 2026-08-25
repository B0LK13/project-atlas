# AS-CODER-ALPHA-ACTIONS-LEDGER-MCP-001 — vault-scoped action ledger

Read-only Coder Alpha projection of the reconstructable web action ledger.

Package ID: `AS-CODER-ALPHA-ACTIONS-LEDGER-MCP-001`.

## What this is

- Existing `GET /v1/actions` (contract unchanged)
- MCP tool `atlas.actions.ledger.read` — zero-arg
- Web `#/actions` — GET lens only

Missing ledgers are a valid empty projection. This tool never posts actions.

## What this is not

- Truth Core / Layer B
- Authority, PILOT, or owner capability
- `POST /v1/actions`
- A healthy/completion signal

Honesty:

- `LEDGER != TRUTH CORE`
- `GET != POST`
- `EMPTY != HEALTHY`
- `MCP != AUTHORITY`
- `UI != CANONICAL`

## Validation

```
.venv/bin/python -m pytest \
  tests/unit/test_as_coder_alpha_actions_ledger_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py -q --no-cov
```
