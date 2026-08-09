# AS-QUERY-MULTI-001 — Tip-safe multi-query plans

| Field | Value |
|---|---|
| Package | `AS-QUERY-MULTI-001` |
| Band | **Tip-safe** (plans only; no graph enrichment) |
| Module | `project_atlas.query_plan` |
| Schema | `query-multi-plan` → `schemas/query-multi-plan.schema.json` |

## What this is

Deterministic **plan envelopes** that batch/order Core query *requests*
(`point` / `multifield` / `list`) across subjects and project scopes.

```text
plan ≠ answer
plan ≠ authority winner
plan ≠ temporal tip
plan ≠ trust score
plan ≠ graph-elevated subject
```

## Ordering

**Caller order preserved** for projects and for items within each project
(QM-FR-011). Identical inputs → byte-identical JSON (`sort_keys=True`).

## Fail-closed

Empty plans, unknown shapes/kinds, malformed items, oversized batches, or
forbidden fields (`trust_*`, `confidence_*`, `graph_*`, answer/value keys)
reject the **entire** plan with `QueryPlanError` (`request_invalid`) and a
structured rejection listing invalids — never silent partial success.

## Explicit non-goals (this band)

- Graph enrichment / resolved-entity sidecars
- Cross-project XPROJ joins
- CLI plan dump (deferred; soft-serialize vs other `cli.py` writers)
- AS-REL-001
- Reopening AS-QUERY-001 `--list` semantics
- Dual-owning AS-EXPLAIN-001 Band A/B writers (optional `attach_explain_receipt`
  is a planning hint only)

## Usage

```python
from project_atlas.query_plan import build_query_plan, plan_to_json

plan = build_query_plan(
    [
        {
            "project_id": "proj-a",
            "items": [
                {"shape": "point", "kind": "authoritative", "subject": "s1", "field": "title"},
                {"shape": "list", "kind": "temporal"},
            ],
        }
    ]
)
print(plan_to_json(plan))
```
