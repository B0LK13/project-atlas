# AS-EXPLAIN-001 — Structured explainability / provenance receipts (Band A)

Band A adds **consume-only** explanation receipts over existing AS-CORE-007/008
answers and AS-QUERY-DIAG diagnostics. Receipts are operational provenance
metadata — never Layer-B/C truth, never authority winners, and never subjective
trust or confidence scores.

## Library

```python
from project_atlas.explain_receipts import (
    build_explain_receipt_from_answer,
    build_explain_receipts_from_multifield,
    build_explain_receipt_from_diagnostic,
    receipt_to_json,
)
from project_atlas.schema import validate_record

receipt = build_explain_receipt_from_answer(answer)
validate_record(receipt, "explain-receipt")
print(receipt_to_json(receipt), end="")
```

## Schema

- Kind: `explain-receipt`
- File: `src/project_atlas/schemas/explain-receipt.schema.json`
- `package: "AS-EXPLAIN-001"`, `schema_version: 1`
- `additionalProperties: false` — score fields cannot be smuggled

## CLI

Optional explain dump is **deferred** this wave (serialize `cli.py` with
AS-QUERY-001). Library receipts are sufficient for Band A.

## Band B

Graph relationship / resolved-entity explain sidecars require a separate
addendum. Missing graph ≠ query failure.

## Invariants

- No trust/confidence scores (EXPL-INV-001)
- No invented claim / authority / temporal values (EXPL-INV-002)
- Absent evidence → structured `omissions` (EXPL-INV-003)
- Deterministic JSON (`sort_keys=True`) (EXPL-INV-005)
- No `knowledge_compiler` / VAL / BACKUP dual-own (EXPL-INV-008)
