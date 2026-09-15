# AS-GRAPH-001 — Graph Artifact Acceptance

**Package:** AS-GRAPH-001  
**Stream:** Atlas Graph Layer (ADR-002 stream 3)  
**Status:** Implementation complete — governor review required  
**Truth boundary:** `GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY`

## Purpose

Core-owned acceptance of inventory/manifest-backed Graphify artifacts:

- versioned JSON Schemas under `src/project_atlas/schemas/`
- deterministic library `project_atlas.graph_acceptance`
- derived-only classification (`graphify-output`, authority `derived`)
- `graphify.semantic_ingestion` default **false** (enabling fails closed until AS-GRAPH-003+)

## Persistence choice

AS-GRAPH-001 is **library + schemas + classification + thin CLI**. It does **not** write:

- `relationships/` canonical stores
- claims / claim identity
- `state/current-state/` or `state/authoritative-state/`
- knowledge-query caches

Acceptance returns an in-memory receipt (`AcceptanceReceipt`). Optional vault receipts under `generated/graph/acceptance/*.json` are validated by `atlas validate` if present; this package does not emit them by default.

## Artifact families

| Basename | Family | Nodes/edges emitted |
|---|---|---|
| `graph.json` | envelope | counted from payload |
| `nodes.json` / `nodes.jsonl` | nodes | nodes only |
| `edges.json` / `edges.jsonl` | edges | edges only |
| `metadata.json` / `.yaml` / `.yml` | metadata | **zero** |

Acceptance requires Core manifest `sources[].path` + `sources[].sha256` binding (heritage `documents[]` also accepted).

## CLI

```bash
atlas accept-graph --source <project-root> --manifest <manifest.json>
```

Reports accepted artifact ids, hashes/counts via inspect summary, and `semantic: disabled`. Exit `1` on fail-closed errors.

## Invariants

- Derived only — never primary/maintained authority ranks
- No fuzzy / LLM identity merge
- No automatic authority / temporal / claim mutation
- Legacy vaults without Graphify artifacts unchanged
- AS-RET semantics unchanged

## Out of scope

AS-GRAPH-002…005 (entity resolution, relationship stores, quarantine/health, projections).
