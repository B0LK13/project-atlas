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

## Inventory depth (deepen-f)

This directory currently contains **one narrative inventory file only**. The
family directories and payload filenames in FIXTURE-PLAN are reserved names;
they do not exist and must not be interpreted as coverage.

| Inventory state | Meaning | Gate value |
|---|---|---|
| reserved | family/scenario name documented | none |
| sketched | positive + negative outcome described in prose | none |
| payload-present | future review payload exists, still non-runnable | none |
| harness-certified | future governor evidence after READY | not available |

Additional reserved family `estate-evidence-class/` exists solely to prevent a
fixture rehearsal or fixture-only waiver from being reported as an authentic
pilot pass. Current state for every family is **reserved/sketched only**.

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
