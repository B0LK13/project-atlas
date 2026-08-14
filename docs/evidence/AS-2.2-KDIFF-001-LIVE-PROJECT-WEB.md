# AS-2.2-KDIFF-001 — Time Machine live project Web journey

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
BRANCH: `cursor/time-machine-live-project-25b1`
BASE: `9441b0c576dc54bc43a92a62a4e972889424c21f`

```
KDIFF != AUTHORITY
UI != CANONICAL_TRUTH
DEMO_STUB != LIVE_VAULT
MERGE_AUTHORIZATION = NOT_GRANTED
```

Not #354. Does not touch Roadmap modules.

## Change

`#/time-machine` accepts `?project=` / `?from=` / `?to=`.
Projects inventory and Knowledge link into the selected project.
Golden-demo defaults remain `harbor-api` / `2024-03-01` / `2024-10-01`.
Empty **live** catalogs stay UNKNOWN. Failed LIVE loads and demo stubs
are not labeled as empty UNKNOWN catalogs.

## Validation

```
apps/web: tsc -b
pytest tests/unit/test_as_2_2_kdiff_live_project_web.py
```
