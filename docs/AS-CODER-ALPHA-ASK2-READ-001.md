# AS-CODER-ALPHA-ASK2-READ-001

Vault-scoped REPORT READ of existing Ask Atlas 2 / `generated/ops/ask` artifacts.

- Surfaces: `atlas ask2-status report|show`, `GET /v1/ask2/report`, MCP `atlas.ask2.read`
- Honesty: ASK2 REPORT != ANSWER; ARTIFACT != AUTHORITY; MODEL != AUTHORITY; UNKNOWN STAYS UNKNOWN
- Existing `atlas ask2 --question` lens is unchanged and is never invoked by this wrap
- Mixed valid + corrupt artifacts roll up as UNKNOWN, not healthy PRESENT
- Same answer id with an altered payload fails closed
- MERGE_AUTHORIZATION = NOT_GRANTED
