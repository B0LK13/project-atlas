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


## Scenario inventory ledger (deepen-g)

| Family | Reserved scenarios | Positive narrative | Negative narrative | Payloads | Runner | Gate credit |
|---|---|---|---|---|---|---|
| federation-smoke | FX-2.0-FED-001/002 | sketched | sketched | absent | absent | none / **NO** |
| ux-command-center | FX-2.0-UX-001/002 | sketched | sketched | absent | absent | none / **NO** |
| provider-adapter | FX-2.0-PROV-001 | sketched | sketched | absent | absent | none / **NO** |
| mcp-readonly-surface | FX-2.0-PROV-002 | sketched | sketched | absent | absent | none / **NO** |
| compat-snapshot | FX-2.0-COMPAT-001 | sketched | sketched | absent | absent | none / **NO** |
| sync-v2-tombstone | FX-2.0-SYNC-001/002 | sketched | sketched | absent | absent | none / **NO** |
| estate-evidence-class | FX-2.0-ESTATE-001 | sketched | sketched | absent | absent | none / **NO** |

A row is not coverage until reviewed payloads and a deterministic runner exist.
Even future fixture success cannot substitute for WEB acceptance, authentic
estate pilot evidence, a certified 1.0 snapshot, or governor authorization.

## Review checklist for future payload proposals (all NO)

- [ ] **NO** — no secrets, credentials, personal data, or raw provider output.
- [ ] **NO** — all paths are synthetic relative paths; no host-specific roots.
- [ ] **NO** — expected results include explicit failure classes.
- [ ] **NO** — byte/digest comparison rule is documented.
- [ ] **NO** — fixture, waiver, acceptance, and pilot evidence classes cannot be conflated.
- [ ] **NO** — proposal remains outside production package data until authorized.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

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

| `openai-importer/` | AS-2.0-PROV-001 | Synthetic chat export; secrets-scan before any future ingest |

