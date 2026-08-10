# Research workspace — architecture (PREP)

Package: **AS-2.2-RESEARCH-001**  
Status: **PREP ONLY** — non-normative until 2.2 unlock + contract freeze.

## Problem

Operators and agents need a governed place to investigate a question without
collapsing hypotheses into Layer B authority or inventing estate facts. Today
Ask Atlas is a thin read lens; Research Workspaces + Evidence Packs are the
missing investigation substrate for Atlas 2.2 intelligence.

## Design sketch

```text
                 ┌──────────────────┐
  operator ─────▶│ research-question │
                 └────────┬─────────┘
                          v
                 ┌──────────────────┐
                 │ hypotheses[]     │  competing, ranked
                 └────────┬─────────┘
                          v
                 ┌──────────────────┐
                 │ evidence-ref[]   │  provenance pointers only
                 └────────┬─────────┘
                          v
                 ┌──────────────────┐
                 │ conflicts[]      │  retained incompatibilities
                 └────────┬─────────┘
                          v
                 ┌──────────────────┐
                 │ synthesis        │  bounded; UNKNOWN explicit
                 └────────┬─────────┘
                          v
                 ┌──────────────────┐
                 │ evidence-pack    │  Ask Atlas 2 / agent consume
                 └──────────────────┘
```

## Compiler rules (fail-closed)

1. **Question bound** — every downstream artifact references `question_id`.
2. **Hypothesis ≠ winner** — hypotheses stay `open` / `supported` / `refuted` /
   `inconclusive`; never auto-promote to claim authority.
3. **Evidence class match** — refs declare `evidence_class`; fixture cannot
   satisfy `authentic_estate` questions.
4. **Conflict retention** — material incompatibilities produce conflict rows;
   synthesis must surface them (no silent pick).
5. **Unknown slots** — unanswered facets remain `UNKNOWN` (Ask Atlas contract).
6. **No invention** — absent pointers ⇒ incomplete pack; never synthesize facts.
7. **Determinism** — pack body omits wall-clock; `generated.by` only (NFR-001).
8. **Non-authority** — packs never write Layer B; never set claim winners.
9. **Secrets hygiene** — findings metadata-only; never embed matched secrets.

## Evidence classes (controlled vocabulary sketch)

| Class | May support | Must not claim |
|---|---|---|
| `source_document` | Ingested Layer A pointer | Authority winner |
| `claim_pointer` | Existing claim / lineage ref | New claim invent |
| `receipt` | Ops / session / explain receipt | Pilot PASS |
| `fixture_receipt` | Harness / fixture digests | Authentic estate |
| `index_hit` | Lexical / hybrid plan hit | Embeddings product |
| `graph_projection` | Derived graph lens | Graph = authority |
| `temporal_window` | Valid/transaction time bounds | Retroactive rewrite |
| `authentic_estate` | Owner-authenticated pilot only | Fixture waiver |

## Relationship to Ask Atlas / CTX / RET / conflicts

| Substrate | Relationship |
|---|---|
| AS-2.0-WEB-ASK-001 / Ask Atlas live | Ask Atlas 2 deepens answer shape; still UI≠canonical |
| AS-2.0-CTX-001 | Evidence packs may compose into context packs |
| AS-2.0-RET-HYBRID-001 | Retrieval plans may feed evidence-ref candidates |
| AS-CORE-003 conflicts | Conflict rows align with retained lower-authority evidence |

## Out of scope (this prep)

- Python module under `src/project_atlas/`
- CLI `atlas research …` / `atlas ask …` mutation
- Shipping JSON Schema as package data
- Mutating 2.1 live API / MCP / web / authz / retrieval defaults

## Promotion gate (future)

Implementation opens only after:

1. `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
2. Charter + compat pin packages
3. Contract freeze checklist for `research-*` schemas
