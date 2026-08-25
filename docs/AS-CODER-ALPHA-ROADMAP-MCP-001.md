# AS-CODER-ALPHA-ROADMAP-MCP-001 — vault-scoped roadmap MCP

Read-only MCP wrap over the existing Living Project Roadmap V1 lens
(`AS-PROJECT-ROADMAP-001`). Agents can ask “where is this project, and what
unlocks next?” without inventing a new roadmap compiler.

Package ID: `AS-CODER-ALPHA-ROADMAP-MCP-001`.
Tool ID: `atlas.roadmap.read`.

## What this is

A zero-arg, vault-scoped `vault-read` MCP tool. It iterates `projects/*/`
already visible to `AppService.projects()` and derives each project's
roadmap in memory via `service.roadmap()` → `read_project_roadmap()` →
`build_roadmap_lens()`.

It does **not**:

- accept project / path / write / args keys
- materialize `generated/answers/ans-roadmap-*.json`
- rotate inventories or mutate Layer B
- grant `OWNER_CAPABILITY_GRANTED`
- treat ROADMAP as canonical truth
- invent projects when `projects/` is empty
- fabricate items when a project has no roadmap evidence (UNKNOWN stays UNKNOWN)
- implement D-149 or touch authentic-estate authority

## Honesty

- `ROADMAP != CANONICAL_TRUTH`
- `MCP != AUTHORITY`
- `UI != CANONICAL_TRUTH`
- `UNKNOWN != HEALTHY` (honesty, not a green status)
- `OWNER_CAPABILITY_GRANTED = false` (hard overlay; filesystem availability ≠ owner)
- `DEMO_FIXTURE != AUTHENTIC_PILOT`

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/unit/test_as_coder_alpha_roadmap_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py \
  tests/unit/test_as_2_1_mcp_brief_001.py \
  tests/unit/test_as_2_0_mcp_001.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — INDEPENDENT IV REQUIRED
DO NOT SELF-CERTIFY IV IN THE SAME PASS
NO SELF-MERGE
D149_TOUCHED=NO
```
