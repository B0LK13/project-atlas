# AS-CODER-ALPHA-DOCTOR-MCP-001 — vault-scoped doctor read

Package ID: `AS-CODER-ALPHA-DOCTOR-MCP-001`.

Read-only projection of PROD-DOCTOR-001 `atlas doctor` diagnostics. Agents and
Web can inspect environment/vault signals without treating them as authority
or owner-gate grants.

## Surfaces

- MCP: zero-arg `atlas.doctor.read`
- LIVE_API: `GET /v1/doctor`
- Web: `#/doctor`
- CLI: existing `atlas doctor --json` (unchanged write-free contract)

## Honesty

- `DOCTOR != AUTHORITY`
- `UNKNOWN != HEALTHY`
- `OPERATIONAL HEALTH != OWNER GATE`
- `MCP != WRITE`
- `UI != CANONICAL`
- Empty/missing checks stay UNKNOWN
- This package does not repair vaults or grant owner gates
- `AUTHENTIC_PILOT = NO` unless a later owner-bound run proves otherwise

## Non-goals

- D-149 owner-gate remediation (remains draft `#483`)
- Authentic O2 (`AUTHENTIC_ESTATE_ROOT` unset)
- Merge authorization
