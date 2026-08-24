# Evidence — unknown/changed API + Web

- LIVE_MAIN_HEAD=`f0e0c979e8ead0fdad4cc51682c560299db0a074`
- LIVE_MAIN_TREE=`ba83d96a3542f270ae99c03b59da97b0ce567ac4`
- Branch=`cursor/atlas-autonomous-night-cycle-63c0`
- Packages: `AS-CODER-ALPHA-UNKNOWN-API-001`, `AS-CODER-ALPHA-CHANGED-API-001`, `AS-CODER-ALPHA-UNKNOWN-WEB-001`, `AS-CODER-ALPHA-CHANGED-WEB-001`
- Focused tests: 35 passed
- Related LIVE_API/MCP regression: 53 passed
- Local HTTP smoke: `/v1/meta.unknown_live=true`, `/v1/meta.changed_live=true`, unscoped 400 UNSUPPORTED_SCOPE, missing inventory stays `rollup=baseline` / UNKNOWN history
- D-149: not touched. Main still widens CREDENTIAL+non-estate. Owner-held `#477`.
- MCP for these lenses remains on owner-held `#479`.
- `MERGE_AUTHORIZATION=NOT_GRANTED`
- `AUTHENTIC_PILOT=NO`
