# AS-EXPLAIN-001 — Graph explain sidecars (Band B)

Band B adds **consume-only** graph explain sidecars over public AS-GRAPH-002
resolved nodes / identity explanations and AS-GRAPH-003 relationships.
Sidecars are derived enrichment — never query winners, never authority, and
never subjective trust or confidence scores.

## Library

```python
from project_atlas.explain_graph_sidecars import (
    build_sidecar_from_resolved_node,
    build_sidecar_from_identity_explanation,
    build_sidecar_from_relationship,
    build_graph_absent_sidecar,
    sidecar_to_json,
)
from project_atlas.schema import validate_record

sidecar = build_sidecar_from_resolved_node(resolved_node)
validate_record(sidecar, "explain-graph-sidecar")
print(sidecar_to_json(sidecar), end="")
```

## Schema

- Kind: `explain-graph-sidecar`
- File: `src/project_atlas/schemas/explain-graph-sidecar.schema.json`
- `package: "AS-EXPLAIN-001"`, `schema_version: 1`
- `additionalProperties: false` — score fields cannot be smuggled
- Categorical GRAPH-002 identity labels map to `identity_confidence_label`
  (never a field named `confidence`)

## Fail-closed dispositions

| Disposition | Meaning |
|---|---|
| `present` | Sidecar built from public graph contracts |
| `absent` | Graph inputs missing — **≠ query failure** (EXPL-FR-B01) |
| `refused_hash_mismatch` | Artifact hash mismatch — enrichment withheld (EXPL-FR-B03) |

## CLI

Optional explain dump remains **deferred** (`cli.py` serialize with QUERY).

## Band A

Band A receipt builders / `explain-receipt` envelope are **CLOSED** — do not
reopen. Band B is a separate additive module.

## Invariants

- No trust/confidence scores (EXPL-INV-001)
- Never elevate graph edges/entities to query winners (EXPL-FR-B02)
- Missing graph ≠ query failure (EXPL-INV-004 / EXPL-FR-B01)
- Deterministic JSON (`sort_keys=True`) (EXPL-INV-005)
- No GRAPH-004 quarantine / XPROJ-002 dual-own
