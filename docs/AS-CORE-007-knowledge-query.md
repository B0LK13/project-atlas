# AS-CORE-007 — Knowledge Query Contract

**Status:** Implementation package  
**Trust model:** consume-only over AS-CORE-005 / AS-CORE-006 persisted state  
**Persistence impact:** none

## Purpose

Provide a deterministic, read-only product interface for questions of the form
`(project, subject, field)` that joins:

1. temporal dispositions (`state/current-state/`) — AS-CORE-005  
2. authoritative dispositions (`state/authoritative-state/`) — AS-CORE-006  
3. immutable claim provenance (`state/claims/`)

Query **does not** produce new truth. It surfaces certified compiled state.

## Pipeline position

```text
immutable claims
  → AS-CORE-005 temporal disposition
  → AS-CORE-006 authority evaluation
  → derived authoritative state
  → AS-CORE-007 knowledge query (read-only consumer)
```

## Distinction from AS-RET-001

| Surface | Role |
|---|---|
| **AS-RET-001** (`VaultRetriever`) | Lexical exact/prefix lookup over generated indexes |
| **AS-CORE-007** (`atlas query`) | Certified truth answers from temporal + authoritative state |

AS-RET kind `authority` means **source-rank** records under `state/authority/`
(AS-CORE-003). It is **not** domain authority.

Domain-authority answers use query kinds `authoritative` / `explain` reading
`state/authoritative-state/`.

## Temporal ≠ authoritative

Temporal current and authoritative current are distinct (AS-CORE-007-INV-004).

- A temporally current claim is not automatically authoritative.
- An authoritative role does not resurrect a temporally historical claim.
- Query envelopes always expose both layers separately when available.

## Compilation-snapshot semantics

Answers are relative to the vault’s persisted `compilation_id` for the project.
There is **no** wall-clock / as-of datetime query in AS-CORE-007.

If `compilation_id` differs across present state layers, query fails closed
(`compilation_mismatch`).

## Query kinds

| Kind | Behavior |
|---|---|
| `authoritative` | Disposition + value only when disposition is `authoritative` |
| `temporal` | Temporal disposition only; never sets authoritative value |
| `explain` | Combined envelope from persisted rationales (no inference) |
| `--list` | Deterministic catalog of authoritative-state records |

## Fail-closed / non-answers

| Condition | Result |
|---|---|
| Disposition `authority-pending` / `authority-conflict` / `unresolved` | Structured non-answer; `value=null` (exit 0) |
| No record for subject+field | `status=not_found` (exit 0) |
| Missing / corrupt / mismatched state | Integrity error (CLI exit 1); no invented value |

**Never invent a value** from newest claim, file order, lexical order, or raw
source content.

## CLI

```bash
atlas query --vault <vault> --project <id> --subject <s> --field <f> \
  [--kind authoritative|temporal|explain] [--format json]

atlas query --vault <vault> --project <id> --kind authoritative --list
```

Exit codes: `0` structured answer/non-answer, `1` operational/integrity error,
`2` argparse usage error.

Library entry points: `project_atlas.knowledge_query.query_knowledge`,
`list_authoritative`, `answer_to_json`.

## Example (acceptance fixture)

After compiling the AS-ID-001 receipt corpus:

```bash
atlas query --vault .tmp/vault --project project-atlas \
  --subject wp:AS-ID-001 --field title --kind authoritative
```

Expected:

- `authority_disposition`: `authoritative`
- `value`: `Durable Source Lineage Identity`
- `rule_id`: `R-TITLE-001`
- temporal layer remains distinct (`authority-pending` / title-collapse)

## Read-only guarantee

Query never writes vault files, never regenerates indexes, and never calls
`evaluate_conflicts` or `evaluate_authority`.

## Non-goals (not implemented)

- New authority registry rules  
- Wall-clock as-of history  
- Semantic / vector search  
- Portfolio / Layer C  
- Control Plane mutation  
- Persistence / migration changes  
