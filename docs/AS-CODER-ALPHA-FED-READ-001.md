# AS-CODER-ALPHA-FED-READ-001

Vault-scoped REPORT READ of existing federation artifacts under
`generated/ops/federation/` and `generated/federation/`.

- Surfaces: `atlas federation report|show`, `GET /v1/fed/report`, MCP `atlas.fed.read`
- Honesty: FED != AUTHORITY; FED != CROSS-VAULT PROMOTE; LENS != TRUTH CORE
- Never calls `build_federation_read_lens` or `build_join_inventory`
- Existing `atlas federation join` is unchanged
- MERGE_AUTHORIZATION = NOT_GRANTED
