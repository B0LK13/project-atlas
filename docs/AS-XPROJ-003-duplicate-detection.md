# AS-XPROJ-003 — Duplicate / successor project detection

Package guide for **deterministic duplicate / rename / successor / monorepo
overlap detection**. This is governed portfolio intelligence (Layer C /
derived). It surfaces **review candidates only** — it never auto-collapses
project UUIDs and never silently skips ingest of a live twin.

## Truth boundary

```text
DUPLICATE CANDIDATE ≠ AUTOMATIC UUID COLLAPSE
NAME / STRING ≠ PROJECT IDENTITY
NO AUTOCOLLAPSE / NO UUID REWRITE
```

All emits carry `authority.level = derived` and `autocollapse: false`.

## Allowed signals (deterministic only)

| Signal | Category |
|---|---|
| Canonical remote URL equality (normalized, exact) | `canonical-remote-url-collision` |
| Identity-lock / marker key collision | `identity-lock-collision` |
| AS-ID-001 lineage / retired-slot mapping | `lineage-retired-slot-collision` |
| Explicit successor registration | `explicit-successor` |
| Path-prefix overlap under **approved** monorepo roots | `monorepo-path-prefix-overlap` |

## Forbidden

- Name-only project matching (`match_by_name`)
- Fuzzy / embedding / LLM “same project” (`fuzzy` / `llm`)
- Automatic project UUID rewrite (`rewrite_uuids`)
- Elevating candidates to claims / authority / portfolio winners
- `display_name` / `project_name` / `name` fields on observations

Forbidden attempts emit **rejects** (same schema, `status: reject`) under
`generated/xproj/duplicate-candidates/` — never autocollapse.

## Persistence (frozen)

| Path | Role |
|---|---|
| `generated/xproj/duplicate-candidates/*.json` | Review candidates + rejects |

Never write claims, `state/current-state/`, `state/authoritative-state/`,
knowledge-query caches, Control Plane `relationships/`, Graph Layer paths,
XPROJ-001/002 registry files, or XPROJ-004 `indexes/` / `conflicts/` from this
package.

## Library API

```python
from pathlib import Path
from project_atlas.xproj_duplicates import (
    detect_project_duplicates,
    write_duplicate_outputs,
    inspect_duplicate_detection,
)

result = detect_project_duplicates(
    [
        {
            "project_id": "proj-a",
            "canonical_remote_url": "https://github.com/acme/widgets.git",
        },
        {
            "project_id": "proj-b",
            "canonical_remote_url": "https://github.com/acme/widgets",
        },
    ],
    approved_monorepo_roots=["portfolio/monorepo"],
)
written = write_duplicate_outputs(result, vault=Path("vault"))
```

## Optional CLI

```bash
atlas detect-project-duplicates --projects projects.json [--vault <vault> --write]
atlas detect-project-duplicates --projects projects.json --approved-monorepo-root portfolio/monorepo
```

Both projects remain independently ingestible after candidate emission
(AS-XPROJ-INV-NO-AUTOCOLLAPSE-001).

## Invariants

| ID | Rule |
|---|---|
| AS-XPROJ-INV-NO-AUTOCOLLAPSE-001 | No UUID rewrite / no silent ingest skip |
| AS-XPROJ-INV-NO-FUZZY-001 | No name-merge / fuzzy / LLM identity |
| AS-XPROJ-INV-TRUTH-001 | Candidates ≠ automatic authority |

## Out of scope

- AS-XPROJ-004 conflict intelligence / global indexes (CLOSED on tip — do not dual-own)
- AS-REL-001
- Graph human projections (AS-GRAPH-005)
