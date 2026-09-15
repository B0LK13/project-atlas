# AS-2.1-ASK-ATLAS-LIVE-001 — Web Ask owner packet

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
PR: `#357`
BRANCH: `cursor/web-ask-live-25b1`

```
ASK_STATE = CERTIFIED — MERGE ELIGIBLE
ASK_IV = PASS
ASK_CI = PASS
ASK_PR = 357
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_HELD = YES
```

Cloud does not merge this PR.

---

## Exact pins

```
ACCEPTED_MAIN = 9441b0c576dc54bc43a92a62a4e972889424c21f
PRODUCTION_TIP = 98d364be887f1d671d24603bfdd69354b20bd76b
PRODUCTION_TREE = b96f5db644ca4ede9d7609c4d3c1e1bede4f99a4
```

`PRODUCTION_TIP` is the last production commit. Later docs-only
evidence commits do not change runtime behavior.

---

## Honesty reconciled during IV

- LIVE HTTP/network failures are explicit errors, not `demo_stub`
- Idle (no query) is not labeled UNKNOWN
- Health-keyword hits are shown and are not a health verdict
- `?project=` is a client hint only — ask remains vault-wide lexical
- Matched projects deep-link to Knowledge and Time Machine

---

## Surfaces

- Web: `#/ask?q=&project=`
- API: existing `GET /v1/ask?q=` (unchanged)
- Knowledge: Ask chip preserves project context

```
ASK != AUTHORITY
UI != CANONICAL_TRUTH
MODEL OUTPUT != AUTHORITY
LIVE_FAILURE != DEMO_STUB
IDLE != UNKNOWN
```

---

## Validation observed

```
apps/web tsc -b → pass
pytest tests/unit/test_as_2_1_ask_atlas_live_web.py → 5 passed
Independent static ASK_IV → PASS
Independent LIVE_ASK_IV → PASS
  (empty/long query reject, health tokens, HTTP 400, auth required)
```

Observed GitHub checks on `98d364b`:

- `control-plane` SUCCESS
- `quality (ubuntu-latest, 3.12, full)` SUCCESS
- `quality (ubuntu-latest, 3.13, compat)` SUCCESS
- `quality (windows-latest, 3.12, windows)` SUCCESS

---

## Owner actions required

Review and merge when authorized. Do not infer authorization from
CERTIFIED / CI green / owner absence.

Low-overlap note: KnowledgePage chips also change on #356. The Ask
chip and project-scoped Time Machine chip are additive.

---

## Rollback

Revert this branch. No schema or vault migration.

## Known limitations

- No Playwright e2e in this slice.
- Ask is vault-wide lexical, not a project-scoped or model-backed chat.
