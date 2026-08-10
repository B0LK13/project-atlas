# Compatibility pin — contract stubs (PREP)

Package: **AS-2.2-COMPAT-PIN-PREP-001**

Status: **docs-owned JSON Schema stubs only**. Not promoted to
`src/project_atlas/schemas/` until post-unlock `AS-2.2-COMPAT-PIN-001`.

## Schema index

| Schema | File | Role |
|---|---|---|
| `atlas.2.2.compat-pin-expectation.v0` | [`compat-pin-expectation.schema.json`](compat-pin-expectation.schema.json) | PREP inventory of anchor + consumer expectations |
| `atlas.2.2.compat-pin-scenario.v0` | [`compat-pin-scenario.schema.json`](compat-pin-scenario.schema.json) | Single consumer / drift scenario row |

## Requirement traceability

| ID | Requirement |
|---|---|
| FR-COMPAT-PIN-001 | 2.2 packages declare `compat_snapshot_id` binding |
| FR-COMPAT-PIN-002 | Future 2.1 anchor uses `atlas-2.1.0-compat` snapshot id |
| FR-COMPAT-PIN-003 | PREP fixtures set `release_certified: false` for 2.1 |
| NFR-COMPAT-PIN-001 | No wall-clock timestamps in generated fixture content |
| AT-COMPAT-PIN-001 | Negative fixtures fail closed on release-cert invent |
| AT-COMPAT-PIN-002 | Negative fixtures fail closed on PILOT invent |

## Post-unlock operations (reserved — not implemented)

| Operation | Input | Output |
|---|---|---|
| `compat.expectation.load` | PREP inventory path | Validated expectation record |
| `compat.anchor.verify-2.1` | Published 2.1 anchor path | Pass / drift class report |
| `compat.consumer.require-pin` | Package id + snapshot id | Gate receipt or fail-closed error |

## Non-claims

- Stubs are not package data on this tip
- Operations are not CLI/MCP surfaces on this tip
- `atlas compat verify` continues to verify 1.0 anchor only
