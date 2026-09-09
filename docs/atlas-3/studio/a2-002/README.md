# AS-STUDIO-A2-002 — Mission Journey

```text
AS_STUDIO_A2_002                   = IMPLEMENTED_IN_LANE
BASE                               = certified A2 tip 2debb778 (explicit dependency)
MUTATION                           = NONE
FORMAL_IV                          = NOT_STARTED
MERGE_AUTHORIZATION                = NOT_GRANTED
```

Read-only vertical slice connecting Mission Control, a Knowledge Plane
projection (with provenance honesty states), Development Plane context, and
the existing OWNERSHIP_CLAIM candidates/preview path.

## Documents

| Doc | Role |
|---|---|
| [A2-002-FIRST-WORK-PACKAGE.md](./A2-002-FIRST-WORK-PACKAGE.md) | Scope, acceptance, non-goals |
| [A2-002-EVIDENCE.md](./A2-002-EVIDENCE.md) | Candidate identity + validation |

## CLI

```bash
atlas-studio mission-journey --json
atlas-studio journey --docs-root docs --preview-lane pr/776 --json
```

## Honesty

```text
STUDIO_UI != AUTHORITY
KNOWLEDGE != PERMISSION
DEVELOPMENT_CONTEXT != AUTHORIZATION
PREVIEW != EXECUTION
JOURNEY != MUTATION
CI_PASS != FORMAL_IV
```
