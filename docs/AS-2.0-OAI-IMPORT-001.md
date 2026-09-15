# AS-2.0-OAI-IMPORT-001 — OpenAI importer fixture harness

| Field | Value |
|---|---|
| Package | **AS-2.0-OAI-IMPORT-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **FIXTURE HARNESS** |
| Class | Fixture lane — consumes PROV quarantine; does **not** dual-own PROV |

## Purpose

Deepen `docs/atlas-2.0/fixtures/openai-importer/` into a runnable parse harness:
synthetic chat export → structured fixture receipt (+ optional AS-2.0-PROV-001
quarantine envelope). **No live OpenAI API.**

## Surfaces

| Surface | Path |
|---|---|
| Schema | `openai-import-fixture-receipt` |
| Module | `project_atlas.openai_importer_fixtures` |
| CLI | `atlas openai-import parse` |
| Docs fixtures | `docs/atlas-2.0/fixtures/openai-importer/` |
| Vault output | `generated/ops/openai-import-fixtures/<receipt_id>.json` |

## Invariants

- `live_api = false` always
- Secrets findings are metadata-only (`content_redacted=true`)
- Quarantine path **consumes** `project_atlas.provider_adapters.quarantine_provider_output`
- Does **not** modify PROV registry schemas or dual-own PROV/KCI/RET/TEMPORAL
- Bound to `atlas-1.0.0-compat`

## Explicit non-claims

- Not production MCP / OpenAI SDK wiring
- Not authentic estate PILOT
- Not provider adapter sole-writer (PROV remains sole owner of registry/quarantine schemas)
