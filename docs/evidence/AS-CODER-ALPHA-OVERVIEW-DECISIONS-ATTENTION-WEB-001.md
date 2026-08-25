# Evidence — overview / decisions / attention API + Web

- LIVE_MAIN_HEAD=`f0e0c979e8ead0fdad4cc51682c560299db0a074`
- LIVE_MAIN_TREE=`ba83d96a3542f270ae99c03b59da97b0ce567ac4`
- Branch=`cursor/atlas-autonomous-night-cycle-63c0`
- Packages: `AS-CODER-ALPHA-OVERVIEW-API-001`, `AS-CODER-ALPHA-OVERVIEW-WEB-001`, `AS-CODER-ALPHA-DECISIONS-API-001`, `AS-CODER-ALPHA-DECISIONS-WEB-001`, `AS-CODER-ALPHA-ATTENTION-API-001`, `AS-CODER-ALPHA-ATTENTION-WEB-001`
- Focused + nav + demo-readiness tests: 55 passed (prior to this receipt; honesty/API/web/nav)
- Independent IV of working tree: PASS (`D149_TOUCHED=NO`, `WRITES=NO`, `HARBOR_DEFAULT=NO`, 46 focused)
- Local HTTP smoke: `/opt/cursor/artifacts/overview-decisions-attention-api-receipt.json`
  - unscoped `/v1/overview` → 400 `UNSUPPORTED_SCOPE`
  - traversal `/v1/attention?project=../escape` → 400 `MALFORMED_INPUT`
  - harbor overview/decisions derived; missing portal overview `unknown`
  - attention harbor `BLOCKING` from seeded conflict
  - PATCH → 405 `writes-forbidden`
  - `/v1/meta` overview_live/decisions_live/attention_live=true, write_enabled=false
- D-149: not touched. Blob `e2eafe44` matches `origin/main`. Owner-held `#477`.
- MCP for these lenses not claimed (owner-held `#478` / `#481` surfaces).
- `MERGE_AUTHORIZATION=NOT_GRANTED`
- `AUTHENTIC_PILOT=NO`
