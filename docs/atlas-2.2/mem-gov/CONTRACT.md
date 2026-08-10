# Governed agent memory — contract stubs index

Package: **AS-2.2-MEM-GOV-001** (prep lane `AS-2.2-MEM-GOV-PREP-001`).

Status: **PREP ONLY**. These JSON files are **documentation stubs**, not
installed package schemas and not CI-enforced production gates.

Ship path after unlock (future): `src/project_atlas/schemas/` (or
`src/atlas_contracts/schemas/`) via ADR + freeze.

| Stub file | Artifact | Axis |
|---|---|---|
| `agent-memory-record.schema.json` | Memory unit | Core record |
| `agent-memory-provenance.schema.json` | Provenance block | Provenance |
| `agent-memory-revocation.schema.json` | Revocation event / index row | Revocation |
| `agent-memory-expiry.schema.json` | Expiry evaluation / window | Expiry |
| `agent-memory-supersession.schema.json` | Supersession edge | Supersession |
| `agent-memory-index.schema.json` | Operational index envelope | Projection |

## FR stubs (planning IDs only)

| ID | Requirement stub |
|---|---|
| FR-2.2-MEM-001 | Memory write requires provenance (`content_sha256` + `source_receipt_id` + `session_id`) |
| FR-2.2-MEM-002 | Revoked memory is never returned as active |
| FR-2.2-MEM-003 | Expiry evaluation uses injected `as_of` only (no wall-clock in writers) |
| FR-2.2-MEM-004 | At most one active record per `memory_key` per project scope; supersession is reciprocal |
| FR-2.2-MEM-005 | Memory plane sets `authority_plane=none` and `consume_only=true` |
| NFR-2.2-MEM-001 | Deterministic serialization (`sort_keys`, no `generated.at`) |
| NFR-2.2-MEM-002 | Prep stubs must not alter 2.1 runtime defaults |

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required release gates
- Claiming RELEASE CERTIFIED or PILOT PASS from fixture memory alone
- Writing Layer B notes from memory contents
