# AS-CODER-ALPHA-GRAPH-MCP-001 — vault-scoped impact-graph MCP

Read-only MCP wrap over the existing LIVE_API impact-graph summary
(`GET /v1/graph`, Web `/graph`). Agents get a first-class
`atlas.graph.read` instead of only the side-channel inside
`atlas.explain.receipt.read`.

Package ID: `AS-CODER-ALPHA-GRAPH-MCP-001`.
Tool ID: `atlas.graph.read`.

## What this is

A zero-arg, vault-scoped `vault-read` MCP tool. It calls
`service.graph_summary()` → `impact_graph_summary()` which reads
`generated/indexes/impact-graph.json` when present.

It does **not**:

- fabricate nodes or edges when the graph file is absent or unreadable
- accept an `authority_plane` other than derived/none (those files are
  treated as absent)
- accept project / path / write / args keys
- mutate the vault
- make GRAPH authority
- grant `OWNER_CAPABILITY_GRANTED`
- implement D-149 or touch authentic-estate gates

## Honesty

- `GRAPH != AUTHORITY`
- `MCP != AUTHORITY`
- `ABSENT GRAPH != FABRICATED EDGES`
- `UNKNOWN != HEALTHY`
- `OWNER_CAPABILITY_GRANTED = false`

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/unit/test_as_coder_alpha_graph_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py \
  tests/unit/test_as_coder_alpha_roadmap_mcp_001.py \
  tests/unit/test_as_coder_alpha_mission_workspace_mcp_001.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — INDEPENDENT IV REQUIRED
DO NOT SELF-CERTIFY IV IN THE SAME PASS
NO SELF-MERGE
D149_TOUCHED=NO
```
