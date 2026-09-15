# Research workspace — contract stubs index

Status: **PREP ONLY**. These JSON files are **documentation stubs**, not
installed package schemas and not CI-enforced.

Ship path after unlock (future): `src/project_atlas/schemas/` via ADR + freeze.

| Stub file | Artifact | Stage |
|---|---|---|
| `research-question.schema.json` | Question | 1 |
| `research-hypothesis.schema.json` | Hypothesis | 2 |
| `research-evidence-ref.schema.json` | Evidence pointer | 3 |
| `research-conflict.schema.json` | Conflict | 4 |
| `research-synthesis.schema.json` | Synthesis | 5 |
| `research-evidence-pack.schema.json` | Pack | 6 |
| `ask-atlas-2-answer.schema.json` | Ask Atlas 2 answer lens | consume |

## FR stubs (planning IDs only)

| ID | Requirement stub |
|---|---|
| FR-2.2-RES-001 | Workspace accepts a question and emits a pack covering the full chain |
| FR-2.2-RES-002 | Hypotheses never auto-promote to Layer B claim winners |
| FR-2.2-RES-003 | Conflicts are retained and surfaced in synthesis / Ask Atlas 2 |
| FR-2.2-RES-004 | Missing evidence yields UNKNOWN / INCOMPLETE (never silent certainty) |
| FR-2.2-RES-005 | Ask Atlas 2 answers expose ANSWER/WHY/WHY NOT/EVIDENCE/AUTHORITY/TEMPORAL/CONFLICTS/UNKNOWN |
| FR-2.2-RES-006 | Packs set `authority_promoted=false` and `canonical_write=false` |
| NFR-2.2-RES-001 | Deterministic pack serialization (`sort_keys`, no wall-clock) |
| NFR-2.2-RES-002 | Prep stubs must not alter 2.1 runtime defaults |

## Forbidden until unlock

- Importing these stubs from production modules
- Referencing them from `.github/workflows/ci.yml` as required gates
- Claiming RELEASE CERTIFIED from fixture packs alone
