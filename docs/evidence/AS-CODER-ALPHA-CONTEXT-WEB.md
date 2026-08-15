# AS-CODER-ALPHA-CONTEXT-001 — Web paste-ready agent context

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OWNER-QUEUE-CONSOLIDATION-001`
BRANCH: `cursor/web-agent-context-25b1`
BASE: `689f740f6ebe1bd8c2f5be956235369c924021dc` (exact current main after #360)
PRIOR_BASE: `9441b0c576dc54bc43a92a62a4e972889424c21f`

```
WEB_CONTEXT != ATLAS_CONTEXT_FILE
UI != CANONICAL_TRUTH
LENS != AUTHORITY
DERIVED_CONTEXT != AUTHORITY
UNKNOWN stays UNKNOWN
PR_359_STATE = CERTIFIED — MERGE ELIGIBLE
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

Not #354 / #356 / #357 / #358. Uses existing `GET /v1/brief`.
Does not call `export_agent_context` and does not write context files.
Does not invoke a model.

## Change

`#/context?project=` renders a paste-ready markdown pack from the live
brief so the next agent can be handed current project state without a
re-explanation.

Independent IV (this lane) hardened:

- empty / missing fields stay `UNKNOWN`
- newline / tab flattening so paste bullets cannot inject headings
- selected-project mismatch → no pack
- conversation / session rows with a different `project_id` are dropped
- honesty block states `web_context_is_authority: false`
- runtime Node gates execute the production helper (not source-grep only)

## Local IV

```
FOCUSED_CONTEXT = PASS
HANDOFF_REGRESSION = PASS
RUNTIME_MARKDOWN = PASS
RUFF = PASS
MYPY = PASS
WEB_TYPECHECK = PASS
WEB_BUILD = PASS
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
```

Standard repository CI is observed on the pushed tip (do not guess names).

CI note: GitHub `quality (ubuntu-latest, 3.12, full)` installed mypy 2.3.1
and failed on an unused `type: ignore` in `yaml_structured.py` (unchanged
#359 semantics; present on current main). The ignore is removed so the
required CI gate can complete. This is not a conversational-capture or
context-pack behavior change.

## Rollback

Revert this branch. No schema or vault migration.

## D-099 exact-main refresh

```
REFRESH_METHOD = MERGE_CURRENT_MAIN
REFRESH_BASE = 689f740f6ebe1bd8c2f5be956235369c924021dc
PRODUCTION_SEMANTIC_CONFLICTS = 0
DOCS_ADDITIVE_CONFLICTS = 1 (WORKLOG.md keep-both)
PR359_YAML_CLOSER_PRESENT = YES
DUPLICATE_FIX_REQUIRED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_EXCEPTION_REQUIRED = YES
```

A/B mypy 2.3.1 + types-PyYAML 6.0.12.20260815:

- exact main: unused-ignore at yaml_structured.py:222
- refreshed #359: Success, 187 files

