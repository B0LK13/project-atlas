# AS-CODER-ALPHA-CONFLICTS-MCP-001 — vault-scoped conflicts MCP

Read-only MCP wrap over the existing LIVE_API conflict projection
(`GET /v1/conflicts`). Agents can see unresolved competing claims without
a request-arg protocol and without resolving anything.

Package ID: `AS-CODER-ALPHA-CONFLICTS-MCP-001`.
Tool ID: `atlas.conflicts.read`.

## What this is

A zero-arg, vault-scoped `vault-read` MCP tool. It iterates `projects/*/`
and calls `service.conflicts()` → `list_project_conflicts()`.

It does **not**:

- resolve a conflict or pick a winner
- accept project / path / write / resolve / args keys
- mutate `review/conflicts/` or Layer B
- invent conflicts when `projects/` is empty
- treat an empty/missing conflict file as "resolved"
- grant `OWNER_CAPABILITY_GRANTED`
- implement D-149 or touch authentic-estate gates

Secret-shaped claim values stay redacted by the existing projection
(`NFR-004`). Empty list means "no conflicts recorded", not "healthy" and
not "resolved".

## Honesty

- `CONFLICT PROJECTION != AUTHORITY`
- `CONFLICT PROJECTION != RESOLUTION`
- `EMPTY LIST != RESOLVED`
- `MCP != AUTHORITY`
- `OWNER_CAPABILITY_GRANTED = false`

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/unit/test_as_coder_alpha_conflicts_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py \
  tests/unit/test_as_coder_alpha_graph_mcp_001.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — INDEPENDENT IV REQUIRED
DO NOT SELF-CERTIFY IV IN THE SAME PASS
NO SELF-MERGE
D149_TOUCHED=NO
```
