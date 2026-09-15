# Technical Demo — Operator Script

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> `AS-DEMO-2.1-001` · Hero corpus: `tests/fixtures/demo/estate/`

Run after [QUICKSTART.md](./QUICKSTART.md). Speak the banner aloud at the
start of any audience-facing walkthrough.

## Hero scenario (memorable conflict)

| Signal | Content |
|---|---|
| `harbor-api` architecture docs | Database = **PostgreSQL 15** |
| `harbor-api` implementation note | Runtime pinned to **PostgreSQL 16** |
| `harbor-portal` dependencies | Depends on **harbor-api** HTTP API |
| `harbor-ops` inventory | Several fields intentionally **unknown** |
| Stale ADR in `harbor-api` | Superseded decision left in tree |

Atlas must surface **conflict / stale / unknown** without inventing a winner.

## Narrative (Mode A)

1. **Banner** — Demo is Technical Preview; not authentic pilot; not release evidence.
2. **Discover** — `atlas discover` over `tests/fixtures/demo/estate` inventories three projects.
3. **Ingest** — Sources land under vault Layer A with provenance hashes.
4. **Indexes / validate** — Lexical indexes build; validate exits 0 on clean fixture tip.
5. **Command Center / Projects** — Web or API lists `harbor-api`, `harbor-portal`, `harbor-ops`.
6. **Open harbor-api** — Evidence-backed knowledge appears; no subjective trust scores.
7. **Ask Atlas (positive)** — Question with supporting evidence → answer + citations.
8. **Ask Atlas (unknown)** — Question outside corpus → explicit **UNKNOWN** (no fabrication).
9. **Ask Atlas (conflict)** — “Which PostgreSQL version does harbor-api run?” →
   **CONFLICT / insufficient authoritative resolution** (docs 15 vs impl 16).
10. **Graph / cross-project** — Dependency edge portal → api is visible (projection only;
    Graph is not Layer B authority).
11. **Stale evidence** — Superseded ADR remains labeled stale / superseded, not current truth.
12. **Mission Control / Workspace** — Operational boards load with `demo` / `fixture`
    data-source stamps; `authentic_pilot=false`.
13. **MCP read** — Same project/knowledge facts via allow-listed MCP tools
    (e.g. health / projects.list / knowledge.query — use tip’s certified names).
14. **Controlled op + receipt** — Optional supervised op writes a receipt; reconstruct
    “what happened” from receipt, not from chat memory.
15. **Close** — Restate: DEMO SUCCESS ≠ AUTHENTIC ESTATE CERTIFICATION.

## Suggested Ask Atlas prompts

| Class | Prompt | Expected class |
|---|---|---|
| Positive | “What HTTP API does harbor-portal consume?” | Answer + evidence |
| Unknown | “What is the on-call pager rotation for harbor-ops?” | UNKNOWN |
| Conflict | “Which PostgreSQL major version does harbor-api use?” | CONFLICT / unresolved |

## Failure handling

Any broken step → open `DEMO-FINDING-###` (CRITICAL/HIGH/MEDIUM/LOW).
CRITICAL/HIGH block the label **TECHNICAL DEMO — VERIFIED**.
