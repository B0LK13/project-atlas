# DoD compiler — contract stubs index

Status: **PREP ONLY**. These JSON files are **documentation stubs**, not
installed package schemas and not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

Directory: `docs/atlas-2.2/contracts/dod-compiler/`

| Stub file | Artifact | Stage |
|---|---|---|
| `dod-goal.schema.json` | Goal | 1 |
| `dod-definition.schema.json` | DoD | 2 |
| `dod-criterion.schema.json` | Criterion | 3 |
| `dod-test-binding.schema.json` | Test binding | 4 |
| `dod-evidence-ref.schema.json` | Evidence pointer | 5 |
| `dod-proof-receipt.schema.json` | Proof | 6 |

## FR stubs (planning IDs only)

| ID | Requirement stub |
|---|---|
| FR-2.2-DOD-001 | Compiler accepts a Goal and emits a proof receipt covering the full chain |
| FR-2.2-DOD-002 | Missing evidence or class mismatch yields INCOMPLETE/FAIL (never silent PASS) |
| FR-2.2-DOD-003 | Proof sets `authority_promoted=false` and `consume_only=true` |
| FR-2.2-DOD-004 | Fixture evidence cannot satisfy `authentic_pilot` criteria |
| NFR-2.2-DOD-001 | Deterministic proof serialization (`sort_keys`, no wall-clock) |
| NFR-2.2-DOD-002 | Prep stubs must not alter 2.1 runtime defaults |

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED from fixture proof alone
