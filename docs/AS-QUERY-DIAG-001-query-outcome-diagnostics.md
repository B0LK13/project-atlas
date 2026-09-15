# AS-QUERY-DIAG-001 — Structured Query Outcome Diagnostics

**Status:** Implementation complete — governor review required (MERGE NO)  
**Trust model:** consume-only over AS-CORE-007 / AS-CORE-008 answers + `KnowledgeQueryErrorCode`  
**Persistence impact:** none  
**Normative contract:** `D:\project-atlas-orphans\gen4-next-wave-parallel-001\AS-QUERY-DIAG-001-CONTRACT.md`

## Purpose

Add a small, additive, read-only diagnostic envelope that classifies query
outcomes for machine consumers (including future AS-OBS-001 OPS-SIG-009):

| `outcome_class` | Meaning |
|---|---|
| `answer` | Exit-0 `status=ok` |
| `nonanswer` | Exit-0 certified nonanswer statuses |
| `integrity_failure` | Shared-state / corruption / mismatch / race codes |
| `request_invalid` | Invalid input / unsupported kind |

Honest nonanswer ≠ corruption. Diagnostics are operational metadata — never
Layer-B/C truth and never authority.

## Pipeline position

```text
AS-CORE-007 point query (UNCHANGED semantics)
  → AS-CORE-008 multi-field composition (UNCHANGED semantics)
  → AS-QUERY-DIAG-001 outcome diagnostic envelope (additive projection)
```

## Library API

```python
from project_atlas.knowledge_query import (
    classify_query_outcome,
    query_diagnostic_from_answer,
    query_diagnostic_from_error,
    diagnostic_to_json,
)

classify_query_outcome(answer.status)          # → QueryOutcomeClass
query_diagnostic_from_answer(answer)           # KnowledgeAnswer | KnowledgeMultiFieldAnswer
query_diagnostic_from_error(exc, ...)          # KnowledgeQueryError → QueryDiagnostic
```

Success-path AS-CORE-007 / AS-CORE-008 JSON (`answer_to_json`) remains the
default CLI stdout for exit 0. On `KnowledgeQueryError`, the CLI emits the
diagnostic JSON on stdout and keeps exit code `1`. Argparse usage remains
exit `2` without fabricating a diagnostic.

## Out of scope

Multi-subject / batch / as-of / RET-fill, OBS collectors, Graph, MODEL /
`knowledge_compiler`, authority/temporal recompute.

## Related docs

- `docs/AS-CORE-007-knowledge-query.md`
- `docs/AS-CORE-008-subject-multifield-query.md`
