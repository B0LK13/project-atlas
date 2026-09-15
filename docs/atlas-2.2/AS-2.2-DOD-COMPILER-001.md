# AS-2.2-DOD-COMPILER-001 — Definition-of-Done compiler (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-DOD-COMPILER-001** |
| Prep lane | `AS-2.2-DOD-COMPILER-PREP-001` |
| Branch | `feat/as-2.2-dod-compiler-prep` |
| Status | **PREP ONLY** — docs / contracts / fixtures |
| Unlock | Runtime impl after `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (post `v2.1.0`) |
| Compat posture | Must pin to `v2.1.0` via future `AS-2.2-COMPAT-PIN-001` |
| Tip at prep | `f45134f356a5862e59c9d4c23daa50b912b85598` |
| Evidence root | `D:\project-atlas-orphans\atlas-2.1-productionization-001\` |

## Purpose

Compile a **traceable Definition-of-Done chain**:

```text
Goal → DoD → criteria → tests → evidence → proof
```

Operators and release gates get a deterministic **proof receipt** that either:

- **PASS** — every criterion has bound tests and non-invented evidence, or
- **INCOMPLETE / FAIL** — missing links, wrong evidence class, or contradicted tests (fail-closed).

This package is the **contract + fixture seed** only. It does **not** mutate Core authority, API, authz, or live 2.1 surfaces.

## Pipeline semantics (normative intent; not runtime yet)

| Stage | Artifact | Role |
|---|---|---|
| Goal | `dod-goal` | Named outcome (e.g. release outcome, package DoD) |
| DoD | `dod-definition` | Structured done-definition bound to one Goal |
| Criteria | `dod-criterion[]` | Measurable, fail-closed acceptance rows |
| Tests | `dod-test-binding[]` | Automated / manual / ADV bindings to criteria |
| Evidence | `dod-evidence-ref[]` | Pointers to receipts, CI digests, pilot reports |
| Proof | `dod-proof-receipt` | Compiled PASS / INCOMPLETE / FAIL with full chain |

## Truth boundary

```text
DoD PROOF ≠ LAYER B AUTHORITY
DoD PROOF ≠ PILOT PASS BY ASSERTION
DoD PROOF ≠ LLM SATISFACTION
FIXTURE EVIDENCE ≠ AUTHENTIC ESTATE EVIDENCE
```

- Missing evidence ⇒ **INCOMPLETE**, never silent PASS.
- Evidence class must match criterion class (fixture cannot satisfy `authentic_pilot`).
- Graph rank / UI labels / model prose never satisfy a criterion.

## Surfaces (prep)

| Kind | Path |
|---|---|
| Architecture | `docs/atlas-2.2/dod-compiler/` |
| Contract stubs | `docs/atlas-2.2/contracts/dod-compiler/` |
| Fixture sketches | `docs/atlas-2.2/fixtures/dod-compiler/` |
| ADR | `docs/atlas-2.2/adr/ADR-2.2-DOD-001-dod-compiler-prep.md` |

## Non-claims

- Not production Python module / CLI / schema package data
- Not `ATLAS_2_1_RELEASE_CERTIFIED`
- Not authentic `AUTHENTIC_ESTATE_PILOT=PASS`
- Not a substitute for AS-REL-2.1 / AS-REL-2.2 release checklists
- Not authority promotion or claim compile bypass

## Dependencies (post-unlock)

| Depends on | Why |
|---|---|
| `v2.1.0` / unlock event | Shared production surface freeze |
| `AS-2.2-DOC-CHARTER-001` | Charter + maturity frame |
| `AS-2.2-COMPAT-PIN-001` | Compatibility anchor |
| Soft: `AS-2.2-KCI-001` | Optional KCI harness for criterion unit language |

## Related

- Strategy: `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` (pre-unlock fixtures allowed)
- KCI thin contract (2.0): `docs/AS-2.0-KCI-001.md`
- Explain receipts (1.x substrate): `docs/AS-EXPLAIN-001-explain-receipts.md`
