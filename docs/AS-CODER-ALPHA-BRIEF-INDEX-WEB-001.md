# AS-CODER-ALPHA-BRIEF-INDEX-WEB-001 — vault-scoped brief index

Package ID: `AS-CODER-ALPHA-BRIEF-INDEX-WEB-001`.

First-class production Web page `#/briefs` that lists existing Coder Alpha
project briefs for every project already present in LIVE_API read-status.

## What this is

- Read-only composition of existing `/v1/projects` (via snapshot read-status)
  and existing `/v1/brief?project=`.
- Vault-scoped. The page does not require a `?project=` argument.
- Honest UNKNOWN when inventory is empty or a brief is unavailable.

## What this is not

- Not a new HTTP protocol (`/v1/briefs` is intentionally absent).
- Not `atlas.brief.read` MCP (that tool already exists).
- Not `atlas brief` CLI materialization.
- Not authority. UI ≠ canonical. BRIEF ≠ authority. MCP ≠ authority.
- Not owner-capability grant. `owner_capability_granted=false`.
- Not authentic-pilot certification. `authentic_pilot=false`.
- Not D-149 / authentic-estate / owner-gate work.

## Honesty

- `UI != CANONICAL`
- `BRIEF != AUTHORITY`
- `MCP != AUTHORITY`
- `UNKNOWN != HEALTHY`
- `OWNER_CAPABILITY_GRANTED = false`
- `AUTHENTIC_PILOT = false`
- Demo stub must not fabricate brief bodies.

## Tests

```bash
.venv/bin/python -m pytest tests/unit/test_as_coder_alpha_brief_index_web_001.py
```
