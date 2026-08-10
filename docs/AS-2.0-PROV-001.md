# AS-2.0-PROV-001 — Provider adapters (optional)

| Field | Value |
|---|---|
| Package | **AS-2.0-PROV-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (Wave 2) |
| Class | **RWC** — adapters disabled by default |

## Purpose

Optional provider adapter registry and quarantine envelopes. Disabling adapters
leaves the MVP functional. Provider/model output never bypasses secrets scanning
or provenance gates and never writes Layer B authority.

## Surfaces

| Surface | Path |
|---|---|
| Schemas | `provider-adapter-registry`, `provider-quarantine-envelope` |
| Module | `project_atlas.provider_adapters` |
| CLI | `atlas provider registry`, `atlas provider quarantine` |
| Vault outputs | `generated/ops/provider-adapter-registry.json`, `generated/ops/provider-quarantine/` |

## Invariants

- `adapters_enabled = false` by default
- Forbidden capabilities: promote / authority-mutate / claim-compile / vault-write
- Secret findings are metadata-only (`content_redacted=true`)
- Bound to `atlas-1.0.0-compat`
- No OpenAI/MCP SDK shipping in this package

## Non-claims

- Not production MCP server enablement
- Not authentic estate PILOT
- Not Atlas 2.0 RELEASE CERTIFIED
