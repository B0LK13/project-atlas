# AS-2.1-ASK-ATLAS-LIVE-001 — Web Ask live journey

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
BRANCH: `cursor/web-ask-live-25b1`
BASE: `9441b0c576dc54bc43a92a62a4e972889424c21f`

```
ASK_STATE = CERTIFIED — MERGE ELIGIBLE
ASK_IV = PASS
ASK_CI = PASS
ASK != AUTHORITY
UI != CANONICAL_TRUTH
MODEL OUTPUT != AUTHORITY
LIVE_FAILURE != DEMO_STUB
IDLE != UNKNOWN
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_HELD = YES
```

Not #354. Uses existing `GET /v1/ask`. No Layer B writes.
No new ask backend. `?project=` is a client hint only — the live ask
surface is vault-wide lexical, not project-scoped.

## Change

`#/ask?q=` submits a read-only lexical ask. Empty matches stay UNKNOWN.
Idle (no query) is not labeled UNKNOWN. Demo stub is isolated and used
only when `DEMO_ONLY` is set. Query is encoded and capped at 256
characters. LIVE HTTP/network failures stay explicit errors.
Health-keyword hits are shown and labeled as tokens, not verdicts.
Matched projects deep-link to Knowledge and Time Machine.

## Validation

```
apps/web: tsc -b → pass
pytest tests/unit/test_as_2_1_ask_atlas_live_web.py → 5 passed
ASK_IV = PASS
LIVE_ASK_IV = PASS
CI on 98d364b: control-plane + ubuntu-3.12-full + ubuntu-3.13-compat + windows-3.12 = SUCCESS
```

## Rollback

Revert this branch. No schema or vault migration.
