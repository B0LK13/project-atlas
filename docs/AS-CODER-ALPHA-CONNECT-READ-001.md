# AS-CODER-ALPHA-CONNECT-READ-001

Vault-scoped REPORT READ of existing connect bind/manifest/receipt artifacts.

- Surfaces: `atlas connect-status report|show`, `GET /v1/connect/report`, MCP `atlas.connect.read`
- Honesty: CONNECT != PILOT; MANIFEST != TRUTH CORE; RECEIPT != AUTHORITY
- Existing `atlas connect` bind+compile is unchanged
- Never calls `connect_project`
- MERGE_AUTHORIZATION = NOT_GRANTED
