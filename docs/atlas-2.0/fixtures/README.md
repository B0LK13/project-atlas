# Atlas 2.0 — Fixture sketches (docs-only)

Status: **PREP ONLY** — narrative + filename inventory only.
These files are **not** production schemas or runnable harnesses.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`

## Purpose

Reserve fixture family names and document expected sketch contents before any
2.0 production branch opens. See [FIXTURE-PLAN.md](../FIXTURE-PLAN.md) for the
full inventory table.

## Families

| Directory (sketch) | Stub package | Notes |
|---|---|---|
| `federation-smoke/` | AS-2.0-FED-001 | Multi-vault join; ambiguity → quarantine |
| `ux-command-center/` | AS-2.0-UX-001 | Blocked until WEB APPLICATION ACCEPTED |
| `provider-adapter/` | AS-2.0-PROV-001 | Quarantine + provenance gate samples |
| `compat-snapshot/` | AS-2.0-COMPAT-001 | 1.0 snapshot pin consumer |
| `sync-v2-tombstone/` | AS-2.0-SYNC-001 | Tombstone + incremental sync scenarios |
| `mcp-readonly-surface/` | AS-2.0-PROV-001 | MCP consume-only tools; write-deny matrix |

## Creation policy

- Do **not** add JSON/YAML payload files here until IMPLEMENTATION READY.
- Do **not** reference these paths from production code or CI.
- When promoted, fixtures move to `fixtures/atlas-2.0/` with entry-gate approval.

## Cross-references

- Threat model: [THREAT-MODEL.md](../THREAT-MODEL.md) (T-2.0-007, T-2.0-010, T-2.0-012)
- FR stubs: [PACKAGE-CONTRACT-STUBS.md](../PACKAGE-CONTRACT-STUBS.md)
- Compatibility: [COMPATIBILITY.md](../COMPATIBILITY.md)
- Z-wave lanes: [Z-WAVE-INDEX.md](../Z-WAVE-INDEX.md)
- Prototype markers: [PROTOTYPE-MARKERS.md](../PROTOTYPE-MARKERS.md)
