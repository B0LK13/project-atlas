# DoD compiler — architecture (PREP)

Package: **AS-2.2-DOD-COMPILER-001**  
Status: **PREP ONLY** — non-normative until 2.2 unlock + contract freeze.

## Problem

Release and package “done” claims today are scattered across boards, checklists,
orphan evidence, and prose. Atlas needs a **compiler** that turns a Goal into a
**proof receipt** with an unbroken chain:

```text
Goal → DoD → criteria → tests → evidence → proof
```

without letting UI, graph, or LLM text forge satisfaction.

## Design sketch

```text
                    ┌─────────────┐
   operator/goal ──▶│ dod-goal    │
                    └──────┬──────┘
                           v
                    ┌─────────────┐
                    │ dod-def     │  (1:1 with goal_id)
                    └──────┬──────┘
                           v
              ┌────────────────────────┐
              │ dod-criterion[]        │  measurable rows
              └────────────┬───────────┘
                           v
              ┌────────────────────────┐
              │ dod-test-binding[]     │  pytest / ADV / manual
              └────────────┬───────────┘
                           v
              ┌────────────────────────┐
              │ dod-evidence-ref[]     │  digests / paths / receipt IDs
              └────────────┬───────────┘
                           v
                    ┌─────────────┐
                    │ proof       │  PASS | INCOMPLETE | FAIL
                    └─────────────┘
```

## Compiler rules (fail-closed)

1. **Coverage** — every criterion_id referenced by the DoD must appear in proof.
2. **Binding** — every criterion needs ≥1 test binding OR explicit `manual_waiver` with owner class (rare; never for authentic pilot).
3. **Evidence class match** — `evidence_class` on refs must be ⊆ allowed classes on the criterion.
4. **No invention** — absent files / digests ⇒ INCOMPLETE; never synthesize PASS.
5. **Determinism** — proof body omits wall-clock; `generated.by` only (NFR-001 posture).
6. **Non-authority** — proof never writes Layer B; never sets claim winners.
7. **Evidence hygiene** — secrets findings metadata-only; never embed matched secrets.

## Evidence classes (controlled vocabulary sketch)

| Class | May satisfy | Must not claim |
|---|---|---|
| `unit_test` | Local pytest / ruff / mypy gates | Pilot / release cert |
| `integration_test` | Marked integration suite | Authentic estate |
| `adv_matrix` | ADV/SEC row PASS | PILOT PASS |
| `fixture_receipt` | Fixture harness receipts | Authentic PILOT / LIVE estate |
| `ci_digest` | GitHub Actions run digest pin | Release without checklist |
| `ops_receipt` | Supervised ops receipt | Authority promote |
| `authentic_pilot` | Estate pilot report only | Fixture waiver substitute |
| `release_checklist` | REL package checklist row | Auto-cert from proof alone |

## Relationship to KCI / Explain / REL

| Substrate | Relationship |
|---|---|
| AS-2.0-KCI-001 | Optional compile-request envelope consumer; DoD proof ≠ KCI authority |
| AS-EXPLAIN-001 | Evidence refs may point at explain receipts |
| AS-REL-2.x | Proof feeds checklist assembly; does not replace REL package |

## Out of scope (this prep)

- Python module under `src/project_atlas/`
- CLI `atlas dod …`
- Shipping JSON Schema as package data
- Mutating 2.1 live API / MCP / web / authz

## Promotion gate (future)

Implementation opens only after:

1. `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
2. Charter + compat pin packages
3. Contract freeze checklist for `dod-*` schemas
