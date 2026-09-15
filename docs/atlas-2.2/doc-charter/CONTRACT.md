# Charter + maturity matrix — contract index (PREP)

Package: **AS-2.2-DOC-CHARTER-PREP-001**

Status: **PREP ONLY** — docs-owned JSON Schema stubs; **not** shipped as
`src/project_atlas/schemas/` package data.

## Functional requirements (PREP)

| ID | Requirement |
|---|---|
| FR-DOC-CHARTER-001 | Deepen 2.2 prep charter with goals, vocabulary, gates, DAG summary |
| FR-DOC-CHARTER-002 | Publish draft maturity matrix for landed PREP packages |
| FR-DOC-CHARTER-003 | Machine-readable matrix fixture with invariant block |
| FR-DOC-CHARTER-004 | Negative fixtures for release-cert and PILOT-invent forbidden paths |
| FR-DOC-CHARTER-005 | ADR reserving prep boundary without README index conflict |

## Schema stubs (`contracts/`)

| File | Role |
|---|---|
| [`charter-maturity-row.schema.json`](contracts/charter-maturity-row.schema.json) | Single matrix row |
| [`charter-maturity-matrix.schema.json`](contracts/charter-maturity-matrix.schema.json) | Full matrix inventory |

All stubs carry `PREP STUB — not package data` in title/description.

## Fixture bindings

| Fixture | Schema |
|---|---|
| `fixtures/maturity-matrix.fixture.json` | `charter-maturity-matrix` |
| `fixtures/negative-release-certified.expect.json` | (negative envelope; no schema validate) |
| `fixtures/negative-pilot-invent.expect.json` | (negative envelope; no schema validate) |

## Traceability

| Consumer | Relationship |
|---|---|
| `AS-2.2-DOC-CHARTER-001` | Post-unlock production charter + matrix refresh |
| `AS-2.2-COMPAT-PIN-001` | Depends on charter per strategy DAG |
| Landed 2.2 PREP packages | Referenced as matrix rows (read-only inventory) |
