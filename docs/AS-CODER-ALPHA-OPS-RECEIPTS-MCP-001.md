# AS-CODER-ALPHA-OPS-RECEIPTS-MCP-001 — vault-scoped ops receipt inventory

Zero-arg MCP consume of the existing LIVE_API `GET /v1/ops/receipts` inventory.

Package ID: `AS-CODER-ALPHA-OPS-RECEIPTS-MCP-001`.

## Honesty

- Presence ≠ healthy
- UNKNOWN ≠ healthy
- Inventory ≠ completion / PILOT / release certification
- `owner_capability_granted` is hardcoded false
- Default limit only; no request-arg protocol

Web Ops Health already consumes receipts and is unchanged.
