# AS-STUDIO-A2-002 — evidence

```text
PACKAGE                            = AS-STUDIO-A2-002
BRANCH                             = feat/as-studio-a2-002-mission-journey
BASE_HEAD                          = 2debb7784746228c55503a60e55293929a5f5b1c
BASE_TREE                          = 2ae9a6866977a0a18b1113855195cc11838a7b78
BASE_CERTIFICATION                 = A2-001 Formal IV PASS + CI 34376691357
DEPENDS_ON_UNMERGED_A2             = YES (disclosed)
THIS_CANDIDATE_INHERITS_A2_IV      = NO
```

## Modules

| Path | Role |
|---|---|
| `scripts/atlas_studio/mission_journey.py` | Journey builder + knowledge/dev projection |
| `schemas/atlas_studio_mission_journey_v1.schema.json` | Contract |
| `scripts/atlas_studio/cli.py` | `mission-journey` / `journey` command |
| `tests/unit/test_atlas_studio_a2_002_mission_journey.py` | Acceptance tests |

## Local validation (this successor tip)

```bash
.venv/bin/python -m pytest \
  tests/unit/test_atlas_studio_a0.py \
  tests/unit/test_atlas_studio_a1_mission_control.py \
  tests/unit/test_atlas_studio_a1_semantic_boundaries.py \
  tests/unit/test_atlas_studio_a2_governed_claim.py \
  tests/unit/test_atlas_studio_a2_governance_substrate.py \
  tests/unit/test_atlas_studio_a2_review_closure.py \
  tests/unit/test_atlas_studio_a2_002_mission_journey.py \
  -q --override-ini='addopts='
# → 101 passed
PYTHONPATH=scripts .venv/bin/python scripts/atlas-studio.py doctor --json
# → ok true (incl. a2_002_* checks)
```

```text
IMPLEMENTATION_HEAD                = c8ae7c1e6b177bdb11202e6a00c6b5cb2d96fa8d
BRANCH_TIP                         = 62da717a0728cfabe8e139005efe7d05510cb5a2
BRANCH_TREE                        = 426c15cbe1bd6ebb53388a84358c335a51eafad6
NOTE                               = docs-only commits after IMPLEMENTATION_HEAD
                                     do not change runtime behavior; validate at BRANCH_TIP
STUDIO_SUITE                       = 101 passed (at implementation + docs tip)
DOCTOR                             = ok (a2_002_* PASS)
```

## Demonstrated paths

| Path | Evidence |
|---|---|
| Success journey | `test_journey_schema_success_path` |
| Knowledge NONE_FOUND | `test_knowledge_none_found` |
| Knowledge UNAVAILABLE | `test_knowledge_unavailable_without_docs_root` |
| Knowledge STALE (MC stale) | `test_knowledge_stale_when_mc_stale` |
| Knowledge INCOMPLETE | `test_knowledge_incomplete_forced` |
| Docs scan RETRIEVED | `test_docs_root_scan_retrieves_studio_docs` |
| Missing repo prerequisite | `test_development_missing_repo_prerequisite` |
| Preview attached, no execute | `test_preview_attached_without_execution` |
| A1 boundary preserved | `test_a1_mission_control_still_free_of_journey_and_governance` |
| Closed future intents | `test_closed_capabilities_remain_closed` |

## Non-claims

```text
FORMAL_IV                          = NOT_STARTED
CI_EXACT_HEAD                      = PENDING_AFTER_PUSH
UI_BROWSER_VALIDATION              = NOT_APPLICABLE (CLI-first; no UI change in apps/web)
MERGE_AUTHORIZATION                = NOT_GRANTED
A2_001_CERTIFICATION_REUSED        = NO
```
