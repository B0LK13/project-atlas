# AS-CODER-ALPHA-RUNTIME-READ-001

Vault-scoped REPORT READ inventory of the existing Atlas 2.2 runtime
substrate (`generated/indexes` and optional `generated/ops/runtime`).

- Surfaces: `atlas runtime report|show`, `GET /v1/runtime/report`, MCP `atlas.runtime.read`
- Honesty: RUNTIME != AUTHORITY; INDEXES != TRUTH CORE; HYBRID != AUTHORITY
- Existing `atlas runtime hybrid-retrieve` and `compile-context` are unchanged
- Never invokes hybrid retrieval or the context compiler
- Never writes vault state
- MERGE_AUTHORIZATION = NOT_GRANTED
