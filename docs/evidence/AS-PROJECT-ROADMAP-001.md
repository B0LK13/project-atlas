# AS-PROJECT-ROADMAP-001 — Living Project Roadmap V1

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D098-ROADMAP-AUTHENTIC-WEB-CONTEXT-REMEDIATION`
BRANCH: `cursor/as-project-roadmap-001-6f85`
BASE: `9441b0c576dc54bc43a92a62a4e972889424c21f` (accepted main after #353)
PRE_REMEDIATION_PRODUCTION_HEAD: `a9770ce132822dd1035bb663490f3907d68117eb`
PRE_REMEDIATION_PRODUCTION_TREE: `4359ceb7ecd77d3b8680552f25967557f8c70da8`

```
ROADMAP_STATE = LOCAL_RECERTIFICATION_PENDING
CLOUD_IV = PASS
ROADMAP_LOCAL_AUTHENTIC_IV = PENDING_RECHECK
PRIOR_ROADMAP_IV = SUPERSEDED_BY_AUTHENTIC_LOCAL_IV
MERGE_ELIGIBLE = NO
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_HELD = YES
```

Derived projection. Not a D-042 change. Not authorized to merge.

```
ROADMAP != CANONICAL_TRUTH
ROADMAP != AUTHORITY
ROADMAP != PROJECT STATE MUTATION
UI != CANONICAL_TRUTH
DERIVED_STATUS != AUTHORITY
UNKNOWN != HEALTHY
NO EVIDENCE != COMPLETE
percent_complete_is_canonical = false
```

---

## Surface overlap with D-042 / #353

| Path | Overlap |
| --- | --- |
| `src/project_atlas/project_roadmap.py` | NONE (new) |
| `src/project_atlas/web_api/roadmap.py` | NONE (new) |
| `src/project_atlas/schemas/project-roadmap.schema.json` | NONE (new) |
| `apps/web/src/pages/production/RoadmapPage.tsx` | NONE (new) |
| `apps/web/src/hooks/useLiveRoadmap.ts` | NONE (new) |
| `apps/web/src/App.tsx` | NONE (#353 did not edit) |
| `apps/web/src/components/ProdNav.tsx` | NONE |
| `src/project_atlas/app_service.py` | NONE |
| `src/project_atlas/cli.py` | LOW (new `atlas roadmap` hunks; #353 adds capture) |
| `src/project_atlas/api_server.py` | LOW (new GET `/v1/roadmap`; #353 adds POST capture) |
| `src/project_atlas/schema.py` | LOW (new kind; #353 adds conversation-capture) |
| `src/project_atlas/agent_handoff.py` | NOT TOUCHED — agent-context deferred |
| `src/project_atlas/web_api/brief.py` | NOT TOUCHED |
| `apps/web/src/pages/production/KnowledgePage.tsx` | NOT TOUCHED |
| `apps/web/src/hooks/useLiveBrief.ts` | NOT TOUCHED |

```
SURFACE_OVERLAP_WITH_D042 = LOW
AGENT_CONTEXT_INTEGRATION = DEFERRED_UNTIL_D042_MERGE
D094A_SHARED_FILE_EDITS = NONE (lifecycle/next-unlock stay in dedicated modules)
```

D-094A added a separate lifecycle vocabulary so MERGED != CLOSED and
IMPLEMENTED != VERIFIED. Next unlock now returns WHY + smallest
transition. Cloud fixtures only; Dark Factory vault was not executed.

---

## V1 surfaces

- Deterministic model: `atlas.project-roadmap.v1`
- CLI: `atlas roadmap --vault <vault> [--project <id>] [--json]`
- API: `GET /v1/roadmap?project=<id>` (read-only derive; no write)
- Web: `#/roadmap?project=` (UI ≠ canonical; demo stub only when
  `liveApiDemoOnly()`; HTTP/catch failures stay unlabeled as demo)

Agent context (`CURRENT_PROJECT_POSITION` / critical path / blockers) is
deferred so `#353` `agent_handoff.py` is not contaminated.

---

## Incremental connect (measured, not implemented)

50-file no-change reconnect on accepted-main `connect_project`:

```
FIRST_S ≈ 0.47
SECOND_S ≈ 0.50
SECOND still runs discover + ingest + rediscover + ingest_baseline
SECOND_INGESTED = 52 (same as first)
```

Reconnect is structurally redundant and operationally cheap on the
available Cloud fixture. No bounded implementation lane opened.

```
INCREMENTAL_CONNECT_STATE = DORMANT_NO_MATERIAL_VALUE
INCREMENTAL_CONNECT_PR = NONE
```

---

## Overnight IV reconciliation (2026-08-14)

Prior report claimed `ROADMAP_IV=PASS` against stale tip `8f0e78e`.
Live PR head at verification start was `dd6d6f9` / tree `3fc96bc`.
PR body correctly said independent certification pending. Windows CI
was still rolling. Independent falsification of `dd6d6f9` found:

- CRITICAL: selected finished critical path emitted `VERIFIED_COMPLETION`/`CLOSED` while a parallel `NOT_STARTED` item remained
- HIGH: `_conflict_count` counted vault-global `generated/ops/conflicts/*.json`
- HIGH: missing `depends_on` ids were dropped and treated as ready
- HIGH: `state_lens.rollup` was emitted unnormalized (`100% complete`)

```
PRIOR_ROADMAP_IV_CLAIM = STALE_NOT_CERTIFIED
IV_AT_dd6d6f9 = FAIL
REMEDIATION = BOUNDED_ON_THIS_BRANCH
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Gates on this branch

```
pytest tests/unit/test_as_project_roadmap_001.py
       tests/unit/test_as_project_roadmap_web.py
  22 passed against /workspace/src
apps/web tsc -b PASS; vite build PASS
connect materializes ans-roadmap-*; agent-context position after #353
```

## Daytime Web honesty remediation (2026-08-15)

Composed product journey found:

- `JOURNEY_ROADMAP = PARTIAL` — hardcoded `harbor-api`, no `?project=`
- `LIVE_FAILURE_HONESTY = FAIL` on the Roadmap hook (`demo_stub` on error)

`96c4c68` keeps the fixture default when the query is absent, follows
`?project=` otherwise, and sets `data_source=null` on live HTTP/catch
errors. `demo_stub` remains only for explicit `liveApiDemoOnly()`.

```
PRIOR_CERTIFIED_TIP = d0d3afcf548952d15fc3cf80cbb4df63d85012df
ROADMAP_SEMANTICS_TIP = 96c4c68a3d98d64d749231ace7136a8eb8da7ccd
CURRENT_PRODUCTION_TIP = a9770ce132822dd1035bb663490f3907d68117eb
CURRENT_PRODUCTION_TREE = 4359ceb7ecd77d3b8680552f25967557f8c70da8
CI_RUN = 31871795221
KNOWLEDGEPAGE_TOUCHED = NO
ROADMAP_IV = SUPERSEDED_BY_AUTHENTIC_LOCAL_IV
```

---

## Chronology A–G (preserved)

| Step | What | Pin / result |
| --- | --- | --- |
| A | Overnight false-CERTIFIED + honesty defects | `d0d3afc` — hardcoded `harbor-api`, `demo_stub` on live fail |
| B | Query-follow + live-failure honesty | `96c4c68` — follows `?project=`; HTTP/catch `data_source=null` |
| C | CI mypy closer (pre-remediation production) | `a9770ce` / tree `4359ceb7` |
| D | Docs-only recertify | `7a1ce54` — `src/**` and `apps/**` unchanged vs C |
| E | Local D-096 authentic IV | `PARTIAL` — `HARDCODED_HARBOR_API_LEAK=YES`, `WEB_PARITY=FAIL` |
| F | D-098 Cloud Web context remediation | ProdNav preserves `?project=`; Roadmap no silent fixture default |
| G | Local re-IV | `ROADMAP_LOCAL_AUTHENTIC_IV=PENDING_RECHECK` — Cloud does not claim Local PASS |

`PRODUCTION_SEMANTIC_CHANGES_a9770ce_TO_PR_HEAD` before F was `0` (docs/evidence only).

---

## D-098 authentic Web context remediation (2026-08-15)

Local D-096 proved the residual product defect on `a9770ce`:

- ProdNav issued static `/roadmap` (no query preserve)
- `RoadmapPage` `DEFAULT_PROJECT = "harbor-api"`
- Current project `dark-factory-02ee94d0` → nav Roadmap → `GET /v1/roadmap?project=harbor-api`

Bounded Web-only fix on `#354`:

- `ProdNav` reads current `?project=P` and appends `project=P` to Knowledge / Context / Ask / Time Machine / Roadmap / Workspace. Does not copy `from=`/`to=`. Does not hard-code project ids.
- `RoadmapPage` uses explicit `?project=` only. No query → no project / UNKNOWN / require selection. `harbor-api` remains valid only when explicitly selected.
- No Core/API mutation. No global active-project store. No `project-atlas` replacement default.

```
CLOUD_IV = PASS
ROADMAP_LOCAL_AUTHENTIC_IV = PENDING_RECHECK
HARDCODED_HARBOR_API_LEAK = NO  (Cloud source + focused tests; Local recheck required)
WEB_PARITY = PENDING_LOCAL_RECHECK
QUEUE_ORDER_UNCHANGED = YES
```
