# 2.0_INTEGRATION_READINESS_REPORT

Directive: `D-PROJECT-ATLAS-CLOUD-AUTONOMOUS-2.0-PREINTEGRATION-FREEZE`
Recorded: 2026-08-15
Status: **PASS**

This report does not implement LIVE_API or Web.
It does not mutate frozen Wave 9–14 / 003C branch pins.
It does not grant 2.0 package merge authorization.

## 1. Unlock (live-proven)

`#354` body is the D-120 packet (`POST_SEAL_EVIDENCE_COMMIT = NO`).

```
PR354_MERGED = YES
mergedAt = 2026-08-15T13:19:42Z
PR354_POST_MERGE_SEAL = PASS
FINAL_TRAIN_SEAL = PASS
ATLAS_1X_FINAL_TRAIN = CLOSED
ATLAS_2_0_API_WEB_INTEGRATION_GATE = OPEN
POST_MERGE_CI_RUN = 31886914611
POST_MERGE_CI_RESULT = PASS
```

```
FINAL_1X_MAIN_HEAD = e5f17209754558435ac4b7f11ae227aa6e30d2b5
FINAL_1X_MAIN_TREE = 65aac1b362be321bf7faffd3ee832eeddfbcb6de
```

## 2. Frozen autonomous topology

Merge-base with sealed main: `d2d3df478cc1a20f5d88e9f51c5c3e4f066d7f00`
(`Merge pull request #356`).

| Wave | Branch | HEAD | TREE |
|---|---|---|---|
| 9 | `cursor/as-2.0-intel-perf-003-compact-candidates-315e` | `ffca6f60e765da5bc8f14929345461017956bbc4` | `0de7c6c1cc6f88530f9e6882ba86ef51cc207fde` |
| 10 | `cursor/as-2.0-explain-001-graph-315e` | `53e2f8818e19db19b5cb68d12e9ec93df1574cd0` | `838900c7acbb908283957739b403011de1c59d19` |
| 11 | `cursor/as-2.0-gap-002-priority-315e` | `6701916def379309656bc3e33224e021712b462d` | `860cf1923feb563154da924c73589038c3d79830` |
| 12 | `cursor/as-2.0-tempint-001-temporal-315e` | `f5919a07b39e082b6aacbe9a82857219a8db0e48` | `2d798347fcb44873d8b47d608ac92ad68f193c7b` |
| 13 | `cursor/as-2.0-dep-001-explicit-315e` | `d3cfcf85fda4ee6c51693887e4ddf1c07c7d8dec` | `a4e3a2c8e60392060a36c45ccfe646d675a9c1c0` |
| 14 | `cursor/as-2.0-decision-001-candidates-315e` | `19ca85a8cf19c54673dab8df15c4b275dc48ab79` | `0f99f59f470f379924dbe6b60d5423444123de2e` |
| 14+ | `cursor/as-2.0-intel-003c-query-kinds-315e` | `31c0c9cd1e3fd067574a06806a5645e72d31694e` | `7b4d1c3ad884287e7d7ca69ec3d0443c5ebdc44f` |

```
CURRENT_STACK_TIP_HEAD = 31c0c9cd1e3fd067574a06806a5645e72d31694e
CURRENT_STACK_TIP_TREE = 7b4d1c3ad884287e7d7ca69ec3d0443c5ebdc44f
STACK_PIN_MUTATED = NO
```

Stack-only history is Waves 1–14 + 003C library commits. Main-only
history since the merge-base is `#357` Ask-live plus `#354` Roadmap.

## 3. Changed paths

Stack vs sealed main is **93 additive paths**, all under:

- `src/project_atlas/intelligence/`
- `tests/unit/test_as_2_0_*.py`
- `docs/evidence/AS-2.0-*.md`
- `docs/contracts/AS-2.0-INTEL-WAVE*.md`
- `docs/adr/ADR-032-derived-intelligence-is-not-authority.md`

Sealed main has **no** `src/project_atlas/intelligence/` tree.

## 4. Overlap and conflict classification

```
SHARED_PATHS_CHANGED_BOTH_SIDES = 0
git merge-tree --write-tree origin/main 31c0c9c = 0f75e5af484ac1c411d2bfca22f2f9d3a6e464a4
MERGE_TREE_EXIT = 0
CONFLICT_COUNT = 0
PRODUCTION_SEMANTIC_CONFLICTS = 0
UNCLASSIFIED_CONFLICTS = 0
```

Preview vs stack shows sealed-main files that a tip refresh would add
(`api_server.py`, `cli.py`, `App.tsx`, `ProdNav.tsx`, `KnowledgePage.tsx`,
`project_roadmap.py`, Ask/Roadmap web, `#354`/`#357` evidence). Those
paths were not edited on the autonomous stack.

`intelligence/handoff.py` is distinct from main `agent_handoff.py`.

## 5. Schema compatibility

```
INTELLIGENCE_SCHEMA_CATALOG_REGISTRATION = NO
CANONICAL_LAYER_B_WRITE = NO
MIGRATION_REQUIRED = NO
```

Derived DTOs stay in-memory. Sealed main added `project-roadmap`
to `schema.py`; the stack does not touch that file.

## 6. API compatibility (Wave 15 planning only)

Existing sealed-main GET surfaces include `/v1/conflicts`, `/v1/kdiff`,
`/v1/ask`, `/v1/roadmap`, `/v1/knowledge`. No `/v1/intelligence/*`,
`/v1/project-state`, `/v1/project-attention`, or `/v1/portfolio-state`.

Wave-6 candidates remain:

- `GET /v1/intelligence/evidence`
- `GET /v1/intelligence/conflicts`
- `GET /v1/intelligence/explain`
- `GET /v1/project-state`
- `GET /v1/project-attention`
- `GET /v1/portfolio-state`

`/v1/intelligence/conflicts` must not replace `/v1/conflicts`.
No POST. No new auth scope. No canonical writes.

## 7. Web / shared-surface overlap (Wave 16 later)

Shared files that Wave 16 must analyze before edit:

- `apps/web/src/App.tsx`
- `apps/web/src/components/ProdNav.tsx`
- `apps/web/src/pages/production/KnowledgePage.tsx`
- `apps/web/src/pages/HomePage.tsx`

Current stack does not modify them. Wave 16 stays blocked until Wave 15
passes.

## 8. Auth / write / migration

```
NEW_WRITE_SCOPE = NO
NEW_AUTH_SCOPE = NO
NEW_POST_VERBS = NO
DESTRUCTIVE_MIGRATION = NO
```

## 9. Performance residual (not downgraded)

```
DENSE_10K_BASELINE_BEFORE = ~8.8s
DENSE_10K_CURRENT = ~3.8s
DENSE_CANDIDATES = 666650
PERFORMANCE_CLASS = MAJOR
NO_PAIR_DROPPED = YES
SEMANTIC_CHANGE = NO
```

## 10. Security

```
NEW_SECURITY_HIGH = 0
NEW_SECURITY_MEDIUM = 0
SECRET_MATERIAL_IN_DERIVED_RECORDS = NO
PATH_TRAVERSAL_SURFACE_ADDED = NO
```

Library-only. Fail-closed wall-clock `now`/`today`. No vault writes.

## 11. Rollback

1. Keep frozen pins as the pre-refresh ancestry.
2. Refresh only on a new branch via `MERGE_CURRENT_MAIN` (no rebase).
3. If refresh regressions fail, abandon the refresh branch; frozen pins
   remain the last known-good 2.0 stack.
4. Do not revert sealed `origin/main`.

## 12. Refresh executed

```
METHOD = MERGE_CURRENT_MAIN
REBASE = NO
REFRESH_BRANCH = cursor/as-2.0-stack-refresh-315e
FROZEN_WAVE_PINS = PRESERVE
OLD_HEAD = 31c0c9cd1e3fd067574a06806a5645e72d31694e
OLD_TREE = 7b4d1c3ad884287e7d7ca69ec3d0443c5ebdc44f
NEW_HEAD = c2a846c7a86bfe955836d4206a7cf6e01de51698
NEW_TREE = 4ab3b37f8fe81e8a05a813b3a99851538ad18b8c
MERGE_PARENT_MAIN = e5f17209754558435ac4b7f11ae227aa6e30d2b5
MERGE_PARENT_STACK = 844feec04ba897de53d266a712261b86f5619e6b
CONFLICT_COUNT = 0
PRODUCTION_SEMANTIC_CONFLICTS = 0
UNCLASSIFIED_CONFLICTS = 0
```

Frozen `cursor/as-2.0-intel-003c-query-kinds-315e` remains `31c0c9c`.

Post-refresh gates:

```
INTELLIGENCE_UNIT = 133 passed
CORE_IDENTITY_TEMPORAL_AUTHORITY_QUERY_ROADMAP = 181 passed, 1 xfailed
RUFF = PASS
MYPY src = PASS
INTELLIGENCE_STACK_REGRESSION = PASS
TRUTH_INVARIANTS = PASS
NEW_SECURITY_HIGH = 0
NEW_SECURITY_MEDIUM = 0
NEW_WRITE_SCOPE = NO
NEW_AUTH_SCOPE = NO
```

## 13. Verdict

```
READINESS = PASS
STACK_REFRESH = PASS
ATLAS_2_0_API_WEB_INTEGRATION_GATE = OPEN
WAVE_15_IMPLEMENTATION = NOT_STARTED
WAVE_16_IMPLEMENTATION = BLOCKED_BY_WAVE_15
MERGE_AUTHORIZATION = NOT_GRANTED
NEW_PRODUCTION_PR_CREATED = 0
NEXT = WAVE 15 read-only API from Wave-6 contracts on a new isolated branch
```

Truth invariants remain:

```
DERIVED_INTELLIGENCE_IS_AUTHORITY = NO
CONTRADICTION_IS_PROVEN_FALSEHOOD = NO
RISK_IS_FACT = NO
GAP_PRIORITY_IS_FACT = NO
DEPENDENCY_IS_INFERRED = NO
DECISION_ENGINE_IS_AUTHORITY = NO
NEXT_ACTION_CANDIDATE_IS_COMMAND = NO
UNKNOWN_IS_VALID = YES
CANONICAL_WRITE = NO
```
