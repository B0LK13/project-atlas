# AS-CODER-ALPHA-CONTEXT-001 — Web paste-ready agent context

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
BRANCH: `cursor/web-agent-context-25b1`
BASE: `9441b0c576dc54bc43a92a62a4e972889424c21f`

```
WEB_CONTEXT != ATLAS_CONTEXT_FILE
UI != CANONICAL_TRUTH
LENS != AUTHORITY
UNKNOWN stays UNKNOWN
MERGE_AUTHORIZATION = NOT_GRANTED
```

Not #354 / #356 / #357 / #358. Uses existing `GET /v1/brief`.
Does not call `export_agent_context` and does not write context files.

## Change

`#/context?project=` renders a paste-ready markdown pack from the live
brief so the next agent can be handed current project state without a
re-explanation.

## Rollback

Revert this branch. No schema or vault migration.
