# AS-2.0-MCP-001 — MCP tool registry (deny-by-default)

| Field | Value |
|---|---|
| Package | **AS-2.0-MCP-001** |
| Class | **RWC** |
| Compat | `atlas-1.0.0-compat` |

## Purpose

Freeze a deny-by-default MCP/tool class registry after PROV + OAI fixture
landings. No live MCP server, no SDK wiring.

## Invariants

- `live_server=false`, `default_policy=deny`
- vault-write / estate-scan cannot be enabled in this package
- Bound to compatibility anchor; 1.0 wins conflicts

## Non-claims

- Not production OpenAI/MCP connectivity
- Not estate PILOT / SYNC / TWIN production
- Not Atlas 2.0 RELEASE CERTIFIED
