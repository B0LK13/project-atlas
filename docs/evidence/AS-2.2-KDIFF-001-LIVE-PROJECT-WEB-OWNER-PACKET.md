# AS-2.2-KDIFF-001 — Time Machine live project Web owner packet

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
PR: `#356`
BRANCH: `cursor/time-machine-live-project-25b1`

```
TIME_MACHINE_STATE = CERTIFIED — MERGE ELIGIBLE
TIME_MACHINE_IV = PASS
TIME_MACHINE_CI = PASS
TIME_MACHINE_PR = 356
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_HELD = YES
```

Cloud does not merge this PR.

---

## Exact pins

```
ACCEPTED_MAIN = 9441b0c576dc54bc43a92a62a4e972889424c21f
PRODUCTION_TIP = 1ac68f3116181d50adf07e56979b1b217d2665a0
PRODUCTION_TREE = 1b1df42b835ba7b04495336c9b3a8ce3534af2b5
```

`PRODUCTION_TIP` is the last production commit (empty-catalog honesty).
Later docs-only evidence commits do not change runtime behavior.

---

## What was reconciled

First IV of `1a397ec` found LIVE HTTP/network failures mislabeled as
`demo_stub`. Honesty fix `aed8cdf` = PASS for that class.

Independent re-IV then found failed/demo loads still rendered as empty
UNKNOWN catalogs. Bounded fix `1ac68f3`: empty UNKNOWN only after a
successful `live_api` read.

---

## Surfaces

- Web: `#/time-machine?project=&from=&to=`
- API: existing `GET /v1/conflicts?project=` and `GET /v1/kdiff`
- Knowledge / Projects: project-preserving Time Machine links

```
KDIFF != AUTHORITY
UI != CANONICAL_TRUTH
LIVE_FAILURE != DEMO_STUB
FAILED_LOAD != EMPTY_UNKNOWN_CATALOG
```

---

## Validation observed

```
apps/web tsc -b → pass
pytest tests/unit/test_as_2_2_kdiff_live_project_web.py → 3 passed
Independent static IV → PASS at aed8cdf and 1ac68f3
```

Observed GitHub checks on `1ac68f3`:

- `control-plane` SUCCESS
- `quality (ubuntu-latest, 3.12, full)` SUCCESS
- `quality (ubuntu-latest, 3.13, compat)` SUCCESS
- `quality (windows-latest, 3.12, windows)` SUCCESS

---

## Owner actions required

Review and merge when authorized. Do not infer authorization from
CERTIFIED / CI green / owner absence.

---

## Rollback

Revert this branch. No schema or vault migration.

## Known limitations

- No Playwright e2e in this slice.
- Default project remains `harbor-api` when the URL has no `?project=`.
