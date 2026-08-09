# AS-GRAPH-002 — Deterministic Graph Entity Resolution

**Package:** AS-GRAPH-002  
**Stream:** Atlas Graph Layer (ADR-002 stream 3)  
**Status:** Implementation complete — governor review required  
**Depends on:** AS-GRAPH-001 (consume acceptance; do not redefine)  
**Truth boundary:** `GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY`

## Purpose

Project-local, deterministic, fail-closed resolution of accepted Graphify nodes to
Atlas entity identifiers:

- frozen precedence (explicit Atlas ID → durable Core ID → mapping table → stable Graphify id)
- categorical confidence + identity-explanation records (never subjective trust/authority scores)
- unresolved / ambiguous / cross-project → quarantine candidates (handoff to AS-GRAPH-004)
- derived-only authority level

## Persistence choice

Default is **library-only**: `resolve_nodes` / `resolve_from_acceptance` return
in-memory `ResolutionResult` objects.

Optional vault emits (CLI `--write --vault`) are restricted to Core-owned derived paths:

| Path | Role |
|---|---|
| `generated/graph/resolved/<project_id>/*.json` | Resolved-node records |
| `generated/graph/resolved/<project_id>/explanations/*.json` | Identity-explanation sidecars |
| `generated/graph/quarantine-candidates/<project_id>/*.json` | Soft quarantine candidates |

**Forbidden:** `relationships/`, claims stores, `state/current-state/`,
`state/authoritative-state/`, knowledge-query caches, and mutation of
`generated/graph/acceptance/` (AS-GRAPH-001 owned).

## Precedence (frozen)

```text
Explicit Atlas entity ID (project-scoped / well-formed)
  → Explicit durable Core identity (source_lineage_id / project_uuid / claim_id)
  → Configured mapping table (project-local, deterministic)
  → Stable project-local Graphify identifier
  → Unresolved / ambiguous → QUARANTINE CANDIDATE (never guess)
```

AS-ID-001 lineage / project UUID / claim_id formulas are **consumed only** — this
package does not redefine or mint authoritative claim identity.

Fail-closed scope rules (Wave7 ADV-G2):

- Node-stamped `project_id` ≠ resolution scope → `cross-project-resolution-forbidden`
- `project_uuid` durable hits require an explicit local UUID binding (`local_project_uuid` / `--project-uuid`); foreign/unbound UUIDs fail closed
- Duplicate Graphify ids with divergent identity payloads → `ambiguous-identity` (never dual winners)

## CLI

```bash
atlas resolve-graph --source <project-root> --manifest <manifest.json>
atlas resolve-graph --source <project-root> --manifest <manifest.json> \
  --mapping <mapping.json> --project-uuid <uuid> --vault <vault> --write
```

Reports resolved/quarantined counts and winning precedence steps. Exit `1` on
fail-closed errors. Does not enable `graphify.semantic_ingestion`.

## Invariants

- `GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY`
- Authority level recorded as `derived`
- No fuzzy / embedding / LLM / recency merge
- No automatic authority / temporal / claim / query mutation
- Cross-project resolution disabled (AS-WP-006 gate not open)
- AS-RET and AS-CORE-005/006/007/008 evaluators unchanged
- AS-GRAPH-001 acceptance semantics unchanged

## Out of scope

AS-GRAPH-003 (edges), AS-GRAPH-004 (durable quarantine/health), AS-GRAPH-005
(projections), AS-WP-006 (cross-project identities).
