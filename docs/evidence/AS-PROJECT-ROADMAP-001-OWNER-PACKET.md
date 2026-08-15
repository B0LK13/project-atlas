# AS-PROJECT-ROADMAP-001 — Owner merge packet

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-OVERNIGHT-GOVERNOR-20260814-001`
PR: `#354`
BRANCH: `cursor/as-project-roadmap-001-6f85`

```
ROADMAP_STATE = REMEDIATED — CI + IV PENDING
ROADMAP_IV = PENDING_REVALIDATION
ROADMAP_PR = 354
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_HELD = YES
```

Cloud does not merge this PR.

---

## Exact pins

```
ACCEPTED_MAIN = 9441b0c576dc54bc43a92a62a4e972889424c21f
D042_MERGED_VIA = #353
PRODUCTION_TIP = 96c4c68a3d98d64d749231ace7136a8eb8da7ccd
PRODUCTION_TREE = 9a034042fb614429c44a6cde242e51ea9d2680e6
```

`PRODUCTION_TIP` is the last production commit (Web `?project=` routing
+ live-failure honesty). Any later docs-only evidence commit on this
branch does not change runtime behavior.

Daytime governor `D-PROJECT-ATLAS-CLOUD-DAYTIME-GOVERNOR-20260815-001`
found two MEDIUM journey defects on the prior certified tip:

- Roadmap Web hardcoded `harbor-api` (no `useSearchParams`)
- `useLiveRoadmap` labeled HTTP/catch failures as `demo_stub`

Bounded remediation stays inside `#354`. Recertification requires
repeated IV + observed GitHub CI on this tip. Do not treat the prior
`d0d3afc` CERTIFIED stamp as current.

---

## What was reconciled

Prior report claimed `ROADMAP_IV=PASS` against stale tip `8f0e78e`.
Live PR governance said certification pending. Independent IV of
`dd6d6f9` **FAIL**:

- CRITICAL: false `VERIFIED_COMPLETION`/`CLOSED` on parallel unfinished work
- HIGH: cross-project conflict bleed
- HIGH: missing `depends_on` treated as ready
- HIGH: unnormalized state-lens rollup

Bounded remediation + isolation follow-up. Independent IV of `2d2a2dc`
(pre-#353 base) = PASS. Owner then merged `#353`. Branch updated onto
`9441b0c` via merge commit (no rebase, no force-push). Post-merge IV of
`69c2de8` = PASS / POST_MERGE_INTEGRITY = PASS. Agent-context position
wired after D-042 landed.

---

## Surfaces

- CLI: `atlas roadmap [--read-only] [--json]`
- API: `GET /v1/roadmap?project=`
- Web: `#/roadmap?project=`
- Connect: materializes `ans-roadmap-*`
- Agent context / handoff: derived you-are-here / next unlock / blockers

```
ROADMAP != CANONICAL_TRUTH
IMPLEMENTED != VERIFIED
MERGED != CLOSED
NO EVIDENCE != VERIFIED
```

---

## Validation observed

```
pytest tests/unit/test_as_project_roadmap_001.py
       tests/unit/test_as_project_roadmap_web.py
  22 passed (workspace src)
apps/web tsc -b PASS
apps/web vite build PASS (72 modules)
Independent IV of 96c4c68 = PENDING (repeat after CI)
Prior IV PASS at 2d2a2dc and 69c2de8 remains historical only
```

---

## Owner actions required

1. Review `#354`.
2. Grant merge authorization explicitly if desired.
3. Merge. Cloud will not infer authorization from CERTIFIED or CI green.

```
MERGES_PERFORMED = 0
```
