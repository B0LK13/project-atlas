# AS-CODER-ALPHA-COMPAT-READ-001

Vault-scoped REPORT READ wrap of the existing Atlas 1.0 compatibility
anchor (`atlas compat verify` / `load_compatibility_anchor`).

- Surfaces: `atlas compat report|show`, `GET /v1/compat/report`, MCP `atlas.compat.read`
- Honesty: COMPAT != AUTHORITY; ANCHOR != TRUTH CORE; CERTIFIED != GA
- Existing `atlas compat verify` is unchanged
- Never writes vault state
- MERGE_AUTHORIZATION = NOT_GRANTED
