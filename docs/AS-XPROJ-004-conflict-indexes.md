# AS-XPROJ-004 — Conflict intelligence + global derived indexes

Package guide for **cross-project conflict intelligence** and **global derived
indexes** built from AS-XPROJ-001 registry state and AS-XPROJ-002 edges.

This is governed portfolio intelligence (Layer C / derived). It is **not**
AS-RET-001 lexical retrieval, claim truth, temporal current, domain authority,
GRAPH-005 human Markdown projections, or XPROJ-003 duplicate detection.

## Truth boundary

```text
CROSS-PROJECT INDEX ≠ AUTOMATIC AUTHORITY
INDEXES ≠ AS-RET-001 LEXICAL INDEXES
CONFLICT REPORT ≠ AUTO-RESOLVE / CLAIM SYNTHESIS
NAME / STRING ≠ IDENTITY MERGE
```

All emits carry `authority.level = derived`.

## In scope

- Deterministic index documents under `generated/xproj/indexes/**`
  (`projects`, `technologies`, `components`, `services`, `relationships`,
  plus empty optional buckets: `agents`, `skills`, `work-packages`,
  `decisions`, `risks`).
- Conflict intelligence under `generated/xproj/conflicts/**`:
  - `explicit-conflicts-with` from XPROJ-002 edges
  - `version-divergence` when same `display_name` + `entity_class` maps to
    ≥2 global IDs spanning ≥2 projects (optional `attributes.version`)
- Library API: `build_xproj_indexes` / `write_xproj_index_outputs`
  (CLI held this window to soft-serialize vs AS-GRAPH-005)

## Out of scope / MUST NOT

- Rewrite AS-RET-001 exact/prefix semantics or write `generated/indexes/`
- Dual-own `graph_projections.py` / `generated/graph/**`
- Write `generated/xproj/duplicate-candidates/**` (AS-XPROJ-003)
- Auto-resolve conflicts / invent Core claim conflicts / elevate authority
- Open AS-REL-001

## Persistence (frozen §7)

| Path | Role |
|---|---|
| `generated/xproj/indexes/<bucket>/index.json` | Global derived index bucket |
| `generated/xproj/conflicts/<conflict_id>.json` | Conflict intelligence report |

## Library usage

```python
from pathlib import Path
from project_atlas.xproj_indexes import build_xproj_indexes, write_xproj_index_outputs

result = build_xproj_indexes(vault=Path("vault"))
written = write_xproj_index_outputs(result, vault=Path("vault"))
```

In-memory fixtures may pass `entities` / `joins` / `edges` without a vault.

## Soft peers

| Peer | Boundary |
|---|---|
| AS-GRAPH-005 | May later consume indexes for human MD; do not dual-own projections |
| AS-XPROJ-003 | Duplicate candidates are separate; 004 may read later, never write |
| AS-RET-001 | Lexical indexes untouched |
