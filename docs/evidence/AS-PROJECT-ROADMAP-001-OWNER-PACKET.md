# AS-PROJECT-ROADMAP-001 — Owner merge packet

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D098-ROADMAP-AUTHENTIC-WEB-CONTEXT-REMEDIATION`
PR: `#354`
BRANCH: `cursor/as-project-roadmap-001-6f85`

```
ROADMAP_STATE = LOCAL_RECERTIFICATION_PENDING
CLOUD_IV = PASS
ROADMAP_LOCAL_AUTHENTIC_IV = PENDING_RECHECK
PRIOR_ROADMAP_IV = SUPERSEDED_BY_AUTHENTIC_LOCAL_IV
ROADMAP_PR = 354
MERGE_ELIGIBLE = NO
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_HELD = YES
```

Cloud does not merge this PR. Cloud does not declare Local authentic IV PASS.

---

## Chronology A–G (preserved)

| Step | What | Pin / result |
| --- | --- | --- |
| A | Overnight false-CERTIFIED + honesty defects | `d0d3afc` |
| B | Query-follow + live-failure honesty | `96c4c68` |
| C | CI mypy closer — pre-remediation production | `a9770ce` / `4359ceb7` |
| D | Docs-only recertify | `7a1ce54` — no `src/**` / `apps/**` delta vs C |
| E | Local D-096 authentic IV | `PARTIAL` — harbor-api nav leak |
| F | D-098 Cloud Web context remediation | this `#354` commit |
| G | Local re-IV | `PENDING_RECHECK` |

---

## Exact pins

```
ACCEPTED_MAIN = 9441b0c576dc54bc43a92a62a4e972889424c21f
CURRENT_ORIGIN_MAIN = 689f740f6ebe1bd8c2f5be956235369c924021dc
CURRENT_ORIGIN_MAIN_TREE = 0ffbda2803237c2d862771b5c0bc710e700aad48
D042_MERGED_VIA = #353
PRE_REMEDIATION_PRODUCTION_HEAD = a9770ce132822dd1035bb663490f3907d68117eb
PRE_REMEDIATION_PRODUCTION_TREE = 4359ceb7ecd77d3b8680552f25967557f8c70da8
LOCAL_D096_RESULT = PARTIAL
HARDCODED_HARBOR_API_LEAK_PRE = YES
WEB_PARITY_PRE = FAIL
CI_RUN_PRE = 31871795221
```

Later docs-only head `7a1ce540` does not invalidate Local runtime on `a9770ce`
(`src/**` and `apps/**` unchanged). `PRIOR_ROADMAP_IV` is superseded by
authentic Local IV. `ROADMAP_STATE` stays `LOCAL_RECERTIFICATION_PENDING`
until Local recheck.

---

## D-098 remediation

Local D-096: current project `dark-factory-02ee94d0` → ProdNav `/roadmap`
with no query → `RoadmapPage` defaulted to `harbor-api`.

Web-only fix:

- `apps/web/src/components/ProdNav.tsx` — project-aware hrefs preserve `?project=P`
- `apps/web/src/pages/production/RoadmapPage.tsx` — no silent fixture default
- Tests: `tests/unit/test_as_project_roadmap_web.py` + `tests/unit/test_as_project_roadmap_nav.py`

`harbor-api` remains valid only when explicitly selected. No
`project-atlas` replacement default. No Core/API mutation. No new PR.

```
CLOUD_IV = PASS
ROADMAP_LOCAL_AUTHENTIC_IV = PENDING_RECHECK
MERGE_ELIGIBLE = NO
QUEUE_ORDER_UNCHANGED = YES
```

---

## Surfaces

- CLI: `atlas roadmap [--read-only] [--json]`
- API: `GET /v1/roadmap?project=`
- Web: `#/roadmap?project=` (no query = UNKNOWN / require selection)
- Connect: materializes `ans-roadmap-*`
- Agent context / handoff: derived you-are-here / next unlock / blockers

```
ROADMAP != CANONICAL_TRUTH
IMPLEMENTED != VERIFIED
MERGED != CLOSED
NO EVIDENCE != VERIFIED
```

---

## Validation observed (Cloud D-098)

```
py -3.12 -m pytest tests/unit/test_as_project_roadmap_001.py
                   tests/unit/test_as_project_roadmap_web.py
                   tests/unit/test_as_project_roadmap_nav.py
  34 passed (20 + 8 + 6)
  prior focused on this PR: 22 (20 + 2)
  delta: +12 (6 new web honesty/routing + 6 new nav)

py -3.12 -m ruff check .     PASS
py -3.12 -m mypy src         PASS (189 files)
cd apps/web && npx tsc -b && npx vite build
  tsc PASS; vite build PASS (72 modules on #354-only tree)
  prior compose vite 76 modules was the 359→358→356→357→354 tree
  (extra Context/Ask pages). #354-only remains 72.

ProdNav-overlap on this branch:
  test_as_web_workspace_001 / ops_health / mission_control / coder_alpha_web
  + Roadmap focused = 58 passed
#359/#358/#356/#357 focused files are not on this branch.
ProdNav still uses `{ to: "/path", label: "..." }` so those compose
assertions remain compatible. QUEUE_ORDER_UNCHANGED=YES.
Expected compose focused after this commit if siblings unchanged:
  37 - 22 + 34 = 49
```

---

## Owner actions required

1. Local re-IV against the D-098 production tip (see
   `D:\atlas-acceptance-d060\roadmap-d096\D098_LOCAL_REIV_HANDOFF.md`).
2. Review `#354` after Local recheck.
3. Grant merge authorization explicitly if desired.
4. Merge. Cloud will not infer authorization from CLOUD_IV or CI green.

```
MERGES_PERFORMED = 0
```
