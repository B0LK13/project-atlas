# AS-CORE-008 — Subject Multi-Field Knowledge Query

**Status:** Implementation package  
**Trust model:** consume-only over AS-CORE-005 / AS-CORE-006 persisted state (same as AS-CORE-007)  
**Persistence impact:** none  
**Predecessor:** AS-CORE-007 Knowledge Query Contract

## Purpose

Provide a deterministic, read-only library primitive for questions of the form
`(project, subject, fields[])` that:

1. Loads project state **once** (shared `compilation_id` snapshot)
2. Answers each requested field with AS-CORE-007 point semantics
3. Returns a multi-field envelope with per-field truth + provenance
4. Never invents values, never recomputes authority/temporal disposition

**Composition ≠ new authority.** Multi-field success ≠ all fields authoritative.

## Pipeline position

```text
immutable claims
  → AS-CORE-005 temporal disposition
  → AS-CORE-006 authority evaluation
  → derived authoritative state
  → AS-CORE-007 point knowledge query (UNCHANGED)
  → AS-CORE-008 multi-field composition (read-only fan-out, one snapshot)
```

## Library API

```python
from project_atlas.knowledge_query import query_knowledge_fields

envelope = query_knowledge_fields(
    vault,
    project_id,
    subject,
    ["title", "package_status"],
    kind="authoritative",  # or temporal | explain
)
```

Envelope (`KnowledgeMultiFieldAnswer`, `package=AS-CORE-008`):

| Field | Meaning |
|---|---|
| `fields` | Caller order, unique |
| `results` | Aligned `KnowledgeAnswer` items (`package=AS-CORE-007`) |
| `compilation_id` | Shared snapshot marker (fail-closed on mismatch) |

No request-level `value`.

## CLI (adapter only)

```bash
# AS-CORE-007 point path (unchanged)
atlas query --vault <vault> --project <id> --subject <s> --field title

# AS-CORE-008 multi-field (repeatable --field)
atlas query --vault <vault> --project <id> --subject <s> \
  --field title --field package_status

# AS-CORE-008 multi-field (--fields CSV)
atlas query --vault <vault> --project <id> --subject <s> \
  --fields title,package_status
```

`--list` remains the authoritative catalog and cannot combine with `--field`/`--fields`.

## Failure classes

| Class | Behavior |
|---|---|
| Request invalid (empty/duplicate fields, bad subject, …) | Fatal; no envelope |
| Shared state invalid (missing/corrupt/mismatch) | Fatal; no partial envelope |
| Field non-answer (`not_found` / pending / conflict / …) | Structured item; CLI exit 0 |
| Internal defect | Fail closed |

## Invariants (selected)

- Single snapshot load; no silent mixed `compilation_id`
- Per-item semantics ≡ point `query_knowledge` under frozen vault
- Caller field order preserved; duplicates rejected
- No AS-RET fallback; no authority/temporal recompute; zero durable mutation
- No cross-field authority laundering

## Out of scope

Generic `QueryItem[]` batch, multi-subject, multi-project, portfolio/Layer C,
aggregation/health, authority expansion, wall-clock as-of, query persistence,
AS-CORE-009+.

See governing contract:
`AS-CORE-008-PACKAGE-CONTRACT.md` (query-scope-lock).
