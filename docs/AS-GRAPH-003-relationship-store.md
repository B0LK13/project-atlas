# AS-GRAPH-003 — Canonical Relationship / Edge Store

**Package:** AS-GRAPH-003  
**Stream:** Atlas Graph Layer  
**Status:** Implementation complete — IV-ready (governor certification required)  
**Depends on:** AS-GRAPH-001 acceptance + AS-GRAPH-002 resolve (consume; do not redefine)  
**Truth boundary:** `GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY`

## Purpose

Normalize accepted Graphify edges against project-local resolved endpoints into
provenance-backed canonical relationship records:

- permanently marked `authority: derived`
- link-quality states `verified` / `supported` / `inferred` (orphaned → quarantine)
- deterministic fingerprint collapse with supporting-artifact retention
- incompatible duplicates → quarantine (never last-write-wins)
- fail-closed on quarantined / cross-project / missing endpoints

**Critical naming rule:** link-quality `verified` ≠ domain-authoritative ≠
knowledge-query authoritative.

## Persistence

Default is **library-only**: `normalize_edges` / `store_from_acceptance`.

Optional vault emits (CLI `--write --vault`) are restricted to:

| Path | Role |
|---|---|
| `generated/graph/relationships/<project_id>/*.json` | Retained derived relationships |
| `generated/graph/relationship-quarantine/<project_id>/*.json` | Soft quarantine candidates (GRAPH-004 handoff) |

**Forbidden:** Control Plane `relationships/`, claims, temporal/authoritative
state, knowledge-query caches, `state/global-entities/`, and mutation of
GRAPH-001/002 emit prefixes.

## MVP relationship types

`part-of`, `depends-on`, `documents`, `validates`, `supersedes`, `derived-from`,
`conflicts-with`  
Unknown types → `extension` (no silent remap). Graph `conflicts-with` never
invents Core claim conflicts.

## CLI

```bash
atlas store-graph --source <project-root> --manifest <manifest.json>
atlas store-graph --source <project-root> --manifest <manifest.json> \
  --mapping <mapping.json> --project-uuid <uuid> --vault <vault> --write
```

Reports retained/quarantined counts and link-quality histogram. Exit `1` on
fail-closed errors (including edge capacity exceeded).

## Invariants

- `GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY`
- Authority level recorded as `derived`
- No fuzzy / embedding / LLM endpoint joining
- No automatic authority / temporal / claim / query mutation
- Cross-project edges forbidden
- AS-GRAPH-001/002 semantics unchanged (freeze)

## Out of scope

AS-GRAPH-004 (durable quarantine/health), AS-GRAPH-005 (human MD projections),
AS-XPROJ-001 (global entities / cross-project edges).
