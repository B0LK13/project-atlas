# AS-CODER-ALPHA-CONTEXT-PACK-READ-001

Vault-scoped REPORT READ of existing context-pack artifacts under
`generated/context/` and `generated/context-compiler/`.

- Surfaces: `atlas context-pack report|show`, `GET /v1/context-pack/report`, MCP `atlas.context-pack.read`
- Honesty: CONTEXT PACK != ESTATE FACTS; PACK != TRUTH CORE
- Never calls `build_context_pack` or `compile_context`
- Existing `atlas context-pack build` is unchanged
- MERGE_AUTHORIZATION = NOT_GRANTED
