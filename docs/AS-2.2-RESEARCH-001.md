# AS-2.2-RESEARCH-001 — Research workspace + Ask Atlas 2 (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-RESEARCH-001** |
| Prep lane | `AS-2.2-RESEARCH-ASK2-PREP-001` |
| Branch | `feat/as-2.2-research-prep` |
| Status | **PREP ONLY** — docs / contracts / fixtures |
| Unlock | Runtime impl after `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (post `v2.1.0`) |
| Compat posture | Must pin to `v2.1.0` via future `AS-2.2-COMPAT-PIN-001` |
| Evidence root | `atlas-2.1-productionization-001` / `D:\project-atlas-orphans\atlas-2.1-productionization-001\` |
| Main at prep | `f45134f` (revalidated; prior evidence tip `a1e0972`) |

## Purpose

Seed a governed **Research Workspace** that turns an operator question into a
deterministic, evidence-backed investigation chain:

```text
question → hypotheses → evidence → conflicts → synthesis → packs
```

Ask Atlas 2 consumes the same chain as a **read-only answer lens** that always
exposes: ANSWER · WHY · WHY NOT · EVIDENCE · AUTHORITY · TEMPORAL VALIDITY ·
CONFLICTS · UNKNOWN.

This package is the **contract + fixture seed** only. It does **not** mutate
Core authority, retrieval live path, API, authz, or 2.1 web production surfaces.

## Pipeline semantics (normative intent; not runtime yet)

| Stage | Artifact | Role |
|---|---|---|
| Question | `research-question` | Scoped inquiry with project / estate bounds |
| Hypotheses | `research-hypothesis[]` | Competing claims under investigation (not truth) |
| Evidence | `research-evidence-ref[]` | Provenance pointers (sources, claims, receipts) |
| Conflicts | `research-conflict[]` | Material incompatibilities retained (fail-closed) |
| Synthesis | `research-synthesis` | Bounded summary with explicit UNKNOWN slots |
| Packs | `research-evidence-pack` | Deterministic pack for agents / Ask Atlas 2 |

## Truth boundary

```text
RESEARCH WORKSPACE ≠ LAYER B AUTHORITY
HYPOTHESIS ≠ CLAIM WINNER
SYNTHESIS ≠ ESTATE FACT INVENTION
ASK ATLAS 2 ≠ CANONICAL WRITE
FIXTURE EVIDENCE ≠ AUTHENTIC ESTATE EVIDENCE
LLM PROSE ≠ AUTHORITY
```

- Missing evidence ⇒ UNKNOWN / INCOMPLETE, never silent ANSWER certainty.
- Lower-authority evidence retained when it conflicts (AS-CORE-003 posture).
- Graph rank / UI labels / model prose never close a conflict.

## Surfaces (prep)

| Kind | Path |
|---|---|
| Architecture | `docs/atlas-2.2/research/` |
| Contract stubs | `docs/atlas-2.2/contracts/research/` |
| Fixture sketches | `docs/atlas-2.2/fixtures/research/` |
| ADR | `docs/adr/ADR-025-research-workspace-prep.md` |

## Non-claims

- Not production Python module / CLI / schema package data
- Not `ATLAS_2_1_RELEASE_CERTIFIED`
- Not authentic `AUTHENTIC_ESTATE_PILOT=PASS`
- Not a replacement for AS-2.0-WEB-ASK-001 / AS-2.1 Ask Atlas live
- Not authority promotion, claim compile bypass, or embeddings product

## Dependencies (post-unlock)

| Depends on | Why |
|---|---|
| `v2.1.0` / unlock event | Shared production surface freeze |
| `AS-2.2-DOC-CHARTER-001` | Charter + maturity frame |
| `AS-2.2-COMPAT-PIN-001` | Compatibility anchor |
| Soft: `AS-2.2-RET-CTX-001` | Hybrid retrieval + context pack production path |
| Soft: `AS-2.2-TEMPORAL-001` | Temporal validity on answers |
| Soft: `AS-2.2-CONFLICT-UX-001` | Conflict projection cockpit |

## Related

- Strategy: `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` (pre-unlock fixtures allowed)
- Ask Atlas 2.0 contract: `docs/AS-2.0-WEB-ASK-001.md`
- Context packs: `docs/AS-2.0-CTX-001.md`
- Claims / authority: `docs/claims-authority-conflicts.md`
- Gap theme: intelligence fabric / Ask Atlas experience (north-star)
