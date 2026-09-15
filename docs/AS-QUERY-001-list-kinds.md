# AS-QUERY-001 — Kind-scoped query `--list` discoverability

Extends `atlas query --list` beyond the tip residual that only accepted
`--kind authoritative`.

## CLI

```bash
atlas query --vault <vault> --project <id> --list --kind authoritative
atlas query --vault <vault> --project <id> --list --kind temporal
```

Unsupported list kinds (including `explain` in v1) fail closed with a structured
AS-QUERY-DIAG `request_invalid` diagnostic (`unsupported_kind`) on stdout and
exit 1.

## Library

```python
from project_atlas.knowledge_query import list_authoritative, list_temporal

auth = list_authoritative(vault, project_id)
temporal = list_temporal(vault, project_id)
```

## Invariants

- Deterministic JSON / stable sort (Q1-INV-001)
- Unsupported kind → fail-closed, never invent rows (Q1-INV-002)
- No dual-own of BACKUP / 001C / EXPLAIN / VAL (Q1-INV-003)
- list ≠ authority winner / temporal tip flip / trust score (Q1-INV-005)
