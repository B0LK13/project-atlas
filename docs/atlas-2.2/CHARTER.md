# Atlas 2.2 — Prep charter (SAFE pre-v2.1.0)

| Field | Value |
|---|---|
| Status | **PREP ONLY** — docs / contracts / fixtures / ADRs / maturity drafts |
| Unlock gate | `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (after `v2.1.0`) |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| Production slot | `AS-2.2-DOC-CHARTER-001` (charter + maturity matrix refresh) |
| PREP package | [`doc-charter/AS-2.2-DOC-CHARTER-PREP-001.md`](doc-charter/AS-2.2-DOC-CHARTER-PREP-001.md) |
| Strategy DAG | [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md) |

## Non-goals

- Reopening or rewriting `v2.0.0` / `v2.1.0` release history, receipts, or waiver posture
- Claiming authentic estate PILOT from fixtures or prep rehearsal
- Elevating Graph / KF2 / FED / PROV / UI / LLM output to Layer B authority
- Unsupervised live writes to protected vault planes
- Relabeling AS-2.0-RET-HYBRID plan harness as 2.2 intelligence certification
- Shipping embeddings or semantic indexes as canonical Layer B truth

## Goals (post-unlock production line)

1. Estate-scale **knowledge intelligence** on certified 2.1 live surfaces
2. Hybrid retrieval + context compiler production path (`AS-2.2-RET-CTX-001`)
3. Governed agent memory, KCI engine, and DoD compiler integration
4. Temporal validity / bitemporal UX with honest unknown handling
5. Conflict projection cockpit and cross-project fabric (consume-only)
6. Reality-gap and estate-ops lenses that never invent health
7. Evidence-backed, fail-closed, LLM≠authority posture throughout

## Maturity vocabulary (normative for audit)

Carried from Atlas 2.1 `CHARTER.md`; applies to 2.2 PREP and post-unlock packages.

| Class | Meaning |
|---|---|
| `LIVE_PRODUCTION` | Operates on real vault/estate inputs with operator controls |
| `LIVE_READ_ONLY` | Live reads only; no mutation path |
| `BOUNDED` | Live or near-live with hard safety envelopes |
| `CONTRACT_ONLY` | Schema/registry/envelope without runtime service |
| `FIXTURE_ONLY` | Synthetic fixtures only |
| `PROTOTYPE` | UI/docs prototype; not production wiring |
| `DRY_RUN` | Plans receipts but forbids live dispatch |
| `DISABLED` | Code path present but fail-closed / off by default |
| `STUB` | Placeholder returning canned structure |
| `DOCUMENTATION_ONLY` | Spec/docs without executable package |
| `SUPERSEDED` | Replaced by a newer package |

Draft matrix: [`doc-charter/FEATURE-MATURITY-MATRIX.md`](doc-charter/FEATURE-MATURITY-MATRIX.md).

## Allowed now (pre-unlock PREP)

- Architecture / ADR sketches under `docs/atlas-2.2/`
- Contract stubs and **docs-only** schema drafts (not `src/project_atlas/schemas/`)
- Fixture sketches and sample JSON under package trees and `docs/atlas-2.2/fixtures/`
- Benchmark harness designs and case inventories under `docs/atlas-2.2/benchmarks/`
- Strategy cross-links and maturity matrix **drafts** that do **not** widen 2.1 release scope
- Charter + matrix PREP under `docs/atlas-2.2/doc-charter/**`
- Unit presence tests for PREP trees (docs/fixtures/ADR only)

## Forbidden until unlock

- Dependency-bearing production mutations of:
  - `src/project_atlas/knowledge_compiler.py`
  - `src/project_atlas/retrieval.py`
  - `src/project_atlas/hybrid_retrieval.py` live semantics / schema version bumps that change 2.1 defaults
- Shipping embeddings as canonical Layer B authority
- Relabeling AS-2.0-RET-HYBRID plan harness as 2.2 intelligence certification
- Fixture waiver for authentic PILOT
- Setting `ATLAS_2_1_RELEASE_CERTIFIED = YES` or `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = YES` on prep tip
- Promoting docs-only schema stubs to shipped package data without explicit unlock ADR

## Truth boundaries (carry forward)

| Boundary | Meaning |
|---|---|
| `HYBRID PLAN ≠ EMBEDDINGS SERVICE / ≠ AUTHORITY` | AS-2.0-RET-HYBRID-001 |
| `SEMANTIC INDEX ≠ CANONICAL TRUTH` | Vectors derived, regenerable, versioned, non-authoritative |
| `UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy` | ADR / 2.1 charter |
| `LLM ≠ authority` | Quarantine-first; provenance required |
| `PREP MATRIX ≠ RELEASE CERTIFICATION` | Maturity drafts do not stamp 2.1/2.2 release credit |
| `FIXTURE REHEARSAL ≠ AUTHENTIC PILOT` | `pilot_roots = 0` on all prep fixtures |

## Relationship to 2.0 / 2.1 / 2.2

| Line | Role |
|---|---|
| AS-RET-001 | Certified lexical exact/prefix retrieval (1.0) |
| AS-2.0-RET-HYBRID-001 | Deterministic hybrid **plan** harness; semantic slot disabled |
| AS-2.0-COMPAT-001 | Live `atlas-1.0.0-compat` anchor consumer |
| AS-2.1 live surfaces | API / MCP / web / sched / L3 — do not regress for 2.2 prep |
| AS-2.2 PREP packages | Docs/contracts/fixtures under `docs/atlas-2.2/**` (see README index) |
| AS-2.2-DOC-CHARTER-001 | Post-`v2.1.0` charter + maturity matrix refresh (production slot) |
| AS-2.2-COMPAT-PIN-001 | Post-unlock 2.1 anchor pin (depends on charter) |
| AS-2.2-RET-HYBRID-001 | Architecture + fixtures + benchmarks for Hybrid Retrieval 2 |
| AS-2.2-RET-CTX-001 | Post-`v2.1.0` production path (hybrid + context packs) |

## Package DAG (summary)

First READY package after unlock per strategy roadmap:

```text
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED
        |
        v
AS-2.2-DOC-CHARTER-001  (charter + matrix refresh)
        |
        +--> AS-2.2-COMPAT-PIN-001
        +--> AS-2.2-KF2-FABRIC-001 / RET-CTX / TEMPORAL / CONFLICT / XPROJ / KCI / …
        |
        v
AS-REL-2.2-001 → v2.2.0
```

Full DAG: [`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md).

## Unlock gates

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Both remain **NO** until authentic `v2.1.0` certification completes. PREP under this charter grants **no** PILOT / WEB / RELEASE credit.
