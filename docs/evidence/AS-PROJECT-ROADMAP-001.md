# AS-PROJECT-ROADMAP-001 — Living Project Roadmap V1

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D094-AND-OVERNIGHT-AUTONOMOUS-DEVELOPMENT-001`
BRANCH: `cursor/as-project-roadmap-001-6f85`
BASE: `c282f2c1eb2dde24f997e480c37d083fda906e54` (accepted main)

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
- Web: `#/roadmap` (UI ≠ canonical; demo stub isolated)

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
pytest tests/unit/test_as_project_roadmap_001.py + test_schema.py
  (adversarial honesty cases added; count is not the gate)
ruff / mypy on touched modules
connect now materializes ans-roadmap-* (agent-context still deferred)
```
