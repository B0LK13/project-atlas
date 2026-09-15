# Hero scenario — Postgres 15 docs vs 16 impl

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> `AS-DEMO-2.1-001` · `fixtures/demo`

## Narrative (memorable)

1. **Project A** architecture / ADR documentation pins the datastore to
   **PostgreSQL 15** (`Deployment: PostgreSQL 15`).
2. **Project A** implementation / runtime evidence pins the same subject to
   **PostgreSQL 16** (`Deployment: PostgreSQL 16`).
3. Atlas surfaces an **unresolved conflict** on subject `doc:harbor-database`
   field `deployment` — it must **refuse false certainty** and must **not**
   invent a winner without authority evidence.
4. **Project B** declares `requires: project-a`, producing a cross-project
   runtime-dependency claim for Graph / impact demos.
5. **Project C** retains a **stale** superseded decision and lists operational
   fields as **unknown** for Ask Atlas UNKNOWN demos.

## Operator beats (demo script hooks)

| Beat | Action | Expected |
|---|---|---|
| Discover | `atlas discover --source fixtures/demo/estate` | 3 projects |
| Ingest | `atlas ingest …` | claims + conflict for Project A |
| Projects | Open Projects lens | `project-a`, `project-b`, `project-c` |
| Knowledge | Open Project A knowledge | conflict / unresolved, not silent pick |
| Ask (conflict) | “Which PostgreSQL major does Project A run?” | CONFLICT / insufficient authority |
| Ask (unknown) | “What is Project C p99 SLO?” | UNKNOWN |
| Graph | Open Graph | Project B → Project A dependency edge |
| Impact | Trace dependents of Project A | Project B visible |

## Authority honesty

Do **not** fabricate a winner. Documentation and implementation disagree.
Until an authoritative resolution source exists, the honest Atlas outcome is
conflict / review — never a silent majority vote.

## Mapping to D01 harbor names (optional)

| This tree | D01 `tests/fixtures/demo` alias |
|---|---|
| `project-a` | `harbor-api` |
| `project-b` | `harbor-portal` |
| `project-c` | `harbor-ops` |
