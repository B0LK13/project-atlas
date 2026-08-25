# AS-CODER-ALPHA-VALIDATE-MCP-001 — vault-scoped validate

Read-only Coder Alpha surface for `atlas validate` over LIVE_API, MCP, and Web.

Package ID: `AS-CODER-ALPHA-VALIDATE-MCP-001`.

## What this is

- `GET /v1/validate` — vault-scoped structural/provenance report
- MCP tool `atlas.validate.read` — zero-arg (`{"tool":"..."}` only)
- Web `#/validate` — read lens over the same projection

The report is the existing `project_atlas.validation.validate()` result plus
an honesty envelope. It does not write the vault.

## What this is not

- Authority, Truth Core, or owner capability
- PILOT / authentic-estate certification
- Release or healthy status
- A project-scoped implicit portfolio
- A substitute for `atlas doctor` (environment diagnostics)

Honesty:

- `OK != HEALTHY`
- `OK != PILOT`
- `OK != RELEASE`
- `VALIDATE != AUTHORITY`
- `MCP != AUTHORITY`
- `UI != CANONICAL`

## Protocol

MCP remains zero-arg. Request keys other than `tool` fail closed (including
`args`, `project`, `path`, `write`). `mcp.read` is required.

Empty or incomplete vaults return `ok=false` with explicit missing-file
errors. That is a valid unknown/failure, not an invented passing report.

## Validation

```
.venv/bin/python -m pytest \
  tests/unit/test_as_coder_alpha_validate_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py -q --no-cov
```
