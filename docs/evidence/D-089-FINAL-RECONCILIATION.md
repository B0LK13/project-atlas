# D-089 — D-049 final pre-merge reconciliation

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-D089-FINAL-RECONCILIATION`
PACKAGE: `AS-CODER-ALPHA-D049-AUTHORIZED-VOLUME-ROOT-001`
PR: `#351` (do not merge)

This packet records Cloud reconciliation after Local D-088 authentic
`D:\` PASS. It may establish `CERTIFIED — MERGE ELIGIBLE`.
It does **not** authorize merge. It does **not** open D-042.
It does **not** change production semantics.

```
PRODUCTION_MUTATION = NO
NEW_PR_CREATED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
D_042_EXECUTION_GATE = CLOSED
```

---

## Lane A — final lineage

Observed 2026-08-14 after `git fetch origin main` and
`git fetch origin cursor/d049-authorized-volume-root-6f85`.

```
CURRENT_MAIN                 = 198350319c17b4de0665f972fda0bc51420cd686
CURRENT_MAIN_TREE            = 2250a7bf1162db778b26a41d94e6e6f7d6b9480c
origin/main                  = 198350319c17b4de0665f972fda0bc51420cd686
D087_PRODUCTION_HEAD         = b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
D087_PRODUCTION_TREE         = 14318297c5fbf40b4fff054ad27126ee4c89db7f
PRE_D089_PR_HEAD             = 568ef533eb04c2de96c1a980848e6e774b8b15d6
PRE_D089_PR_TREE             = bb697c0c869421c220d9925d331978c1c08c2fd9
D087_FREEZE_DESCENDS_FROM_MAIN     = YES
PR_HEAD_DESCENDS_FROM_D087_FREEZE  = YES
```

`git merge-base --is-ancestor 198350319 b2b5d9b` → YES  
`git merge-base --is-ancestor b2b5d9b 568ef53` → YES

Ancestry (oldest → newest on #351):

```
198350319  main
  fcaf4f5  D078 PRODUCTION
  e2f0dfc  D078 evidence
  99aa937  D080 PRODUCTION (historical Local FAIL)
  e8f6ad8  D080 evidence
  13e20b9  D078 superseded-by-D080 note
  8bb8d03  D082 evidence
  cc5c10b  D083 TEST_ONLY
  2fcf818  D084 PRODUCTION (historical correctness PASS / performance SEVERE)
  167b1f6  D084 evidence / D-085 runbook
  b715144  D086 evidence
  b2b5d9b  D087 PRODUCTION FREEZE
  77eb4c1  D087 evidence / D-088 runbook
  568ef53  D042 kickoff retarget (evidence)
```

### D087 freeze → pre-D089 PR head path classification

`git diff --name-status b2b5d9b 568ef53`:

| Path | Class |
| --- | --- |
| `WORKLOG.md` | EVIDENCE_ONLY |
| `docs/backlog.md` | GOVERNANCE_ONLY |
| `docs/evidence/D-042-KICKOFF-PACKET.md` | GOVERNANCE_ONLY |
| `docs/evidence/D-087-CLOUD-IV.json` | EVIDENCE_ONLY |
| `docs/evidence/D-087-SUPERSEDING-FREEZE.md` | EVIDENCE_ONLY |
| `docs/evidence/D-088-LOCAL-REVALIDATION-RUNBOOK.md` | EVIDENCE_ONLY |

No `src/`, `apps/`, or `tests/` path changed after `b2b5d9b`.

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D087_FREEZE = 0
UNRELATED_PRODUCTION_CHANGE = 0
```

### RUNBOOK_PRESENT = NO explanation

```
RUNBOOK_ABSENCE_AT_PRODUCTION_FREEZE_EXPLAINED = YES
```

`docs/evidence/D-088-LOCAL-REVALIDATION-RUNBOOK.md` does **not** exist
in tree `14318297` / commit `b2b5d9b`. It was added later by evidence
commit `77eb4c1`. Local checked out the exact production freeze and
executed the owner-provided Local directive externally. This is not an
acceptance failure.

---

## Lane B — production payload (`main` → D087 freeze)

`git diff --name-status 198350319 b2b5d9b` production / test surface:

| Path | Class | Capability |
| --- | --- | --- |
| `src/project_atlas/cli.py` | PRODUCTION_SEMANTIC | D-078 `--root-mode` |
| `src/project_atlas/estate_discovery.py` | PRODUCTION_SEMANTIC | D-067 / D-078 / D-080 / D-084 / D-087 |
| `src/project_atlas/estate_path_index.py` | PRODUCTION_SEMANTIC | D-087 in-memory path index |
| `src/project_atlas/web_api/discovery.py` | PRODUCTION_SEMANTIC | D-078 root-mode projection |
| `apps/web/src/hooks/useEstateDiscovery.ts` | PRODUCTION_SEMANTIC | D-078 UI root-mode (UI ≠ authority) |
| `apps/web/src/pages/production/DiscoveryPage.tsx` | PRODUCTION_SEMANTIC | D-078 UI root-mode (UI ≠ authority) |
| `tests/unit/test_as_d049_067_high_remediation.py` | TEST_ONLY | D-067 honesty |
| `tests/unit/test_as_d049_078_authorized_volume_root.py` | TEST_ONLY | D-078 |
| `tests/unit/test_as_d049_080_candidate_selection.py` | TEST_ONLY | D-080 |
| `tests/unit/test_as_d049_084_fair_selection.py` | TEST_ONLY | D-084 |
| `tests/unit/test_as_d049_087_path_index_performance.py` | TEST_ONLY | D-087 |

Capability lineage present and expected:

```
D-067  cap/depth honesty
D-078  explicit owner-authorized non-system Windows volume root
D-080  volume root as scope container; fail-closed knowledge relations
D-083  Windows test portability only (cc5c10b, ancestor of D087)
D-084  deterministic_hierarchical_fair_v2 + bounded enrichment
D-087  component-aware in-memory ancestry index + resolved-key reuse
```

No identity-authority widening. No path-safety weakening.
`DISCOVER != CONNECT != INGEST != TRUST != AUTHORITY` remains.

---

## Lane C — observed Cloud / GitHub gates

Do not invent. Observed on pre-D089 tip `568ef53`
(GitHub Actions run `31815051882`, conclusion `success`):

| Check name observed | Result |
| --- | --- |
| `ci / control-plane` | success |
| `ci / quality (ubuntu-latest, 3.12, full)` | success |
| `ci / quality (ubuntu-latest, 3.13, compat)` | success |
| `ci / quality (windows-latest, 3.12, windows)` | success |

Prior Cloud session on D-087 production + evidence also recorded:

```
D049 focused / D063 / D064 / D067 / D078 / D080 / D083 / D084 / D087 = PASS
identity/connect = PASS
source lineage = PASS
ruff = PASS
mypy = PASS
web tsc -b && vite build = PASS
CLOUD_IV = PASS
```

```
KNOWN_CLOUD_GATES = PASS
```

---

## Lane D — Local D-088 applicability

Local receipt (owner-provided; Cloud did not access authentic `D:\`):

```
LOCAL_D088_HEAD = b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
LOCAL_D088_TREE = 14318297c5fbf40b4fff054ad27126ee4c89db7f
VALIDATION_TARGET_STALE = NO
STALE_GLOBAL_ATLAS_USED = NO
OS_NAME = nt
AUTHORIZED_ROOT = D:\
D088_AUTHENTIC_ESTATE_RUN_A = PASS
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
```

Because `PRODUCTION_SEMANTIC_CHANGES_AFTER_D087_FREEZE = 0`:

```
LOCAL_D088_APPLICABLE_TO_CURRENT_PR = YES
```

---

## Local D-088 authentic receipt (recorded, not re-invented)

```
KNOWN_EXPECTED_FOUND = 5/5
OWNER_ANCHORS_STARVED_BY_CAP = 0
NOISY_SUBTREE_MONOPOLY = NO
LARGEST_REGION_EMITTED_COUNT = 104
LARGEST_REGION_EMITTED_SHARE = 0.211
CANDIDATE_SELECTION_POLICY = deterministic_hierarchical_fair_v2
PROJECT_SELECTION_SEMANTIC_DRIFT = 0
KNOWLEDGE_RELATION_SEMANTIC_DRIFT = 0
AUTHORIZED_VOLUME_ROOT_EMITTED_AS_PROJECT = 0
EMPTY / BLANK / DANGLING / VOLUME-CONTAINER relations = 0
FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS = 0
SILENT_IDENTITY_MERGES = 0
SILENT_KNOWLEDGE_MISASSIGNMENT = 0
FALSE_SCAN_COMPLETENESS = 0
PATH_ESCAPES = 0
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
HIGH_OPEN = 0

DIRS_VISITED = 302031
TIME_TO_DISCOVER_PROJECTS = 00:06:25
D079 ≈ 00:10:59
D081 = 01:17:19
D085 = 01:22:01
D087_PERFORMANCE_RESIDUAL = MINOR
FIRST_SCAN_OPERATIONALLY_USABLE = YES
DISCOVERY_OUTPUT_UNDERSTANDABLE = YES
MAJOR_UX_BLOCKER_COUNT = 0

PROJECT_CANDIDATES_SEEN = 11509
PROJECT_CANDIDATES_PRESELECTED = 1500
PROJECT_CANDIDATES_ENRICHED = 1500
PROJECT_CANDIDATES_EMITTED = 493
PROJECT_CANDIDATES_SUPPRESSED = 11016
KNOWLEDGE_CANDIDATES_SEEN = 24666
KNOWLEDGE_CANDIDATES_EMITTED = 500
KNOWLEDGE_CANDIDATES_SUPPRESSED = 24166
BOUNDED_ENRICHMENT_AUTHENTIC = PASS
PATH_RESOLVE_CALLS_DURING_INDEXED_RELATION_MATCHING = 0
KNOWLEDGE_PROJECT_ANCESTRY_CHECKS = 124602
IN_MEMORY_PATH_INDEX_USED = YES
KNOWLEDGE_RELATION_LOOKUP_DOES_NOT_TOUCH_FILESYSTEM_PER_PROJECT = PASS

D078_ROOT_POLICY_REGRESSION = PASS
PATH_PREFIX_COLLISION = PASS
WINDOWS_CASE_PATH_INDEX = PASS

RUN_B_COMPLETED = YES
DOCUMENTATION_LIFT_PROJECT_DISCOVERY = UNCHANGED
DOCUMENTATION_LIFT_KNOWLEDGE_DISCOVERY = IMPROVED
DOCUMENTATION_LIFT_AMBIGUITY = UNCHANGED
DOCUMENTATION_LIFT_EXPLAINABILITY = IMPROVED
DOCUMENTATION_LIFT_AGENT_READINESS = IMPROVED
```

D-075 documentation edits are evidence of documentation quality value.
They are **not** D-049 production payload.

---

## Lane E — D-049 certification

All required pre-merge gates are satisfied:

```
D088_AUTHENTIC_ESTATE_RUN_A = PASS
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
CLOUD_IV = PASS
KNOWN_CLOUD_GATES = PASS
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
HIGH_OPEN = 0
PRODUCTION_SEMANTIC_CHANGES_AFTER_D087_FREEZE = 0
UNRELATED_PRODUCTION_CHANGE = 0
```

Therefore:

```
D_049_MERGE_ELIGIBILITY = YES
D_049_STATE = CERTIFIED — MERGE ELIGIBLE
D_049_FINAL_ACCEPTANCE_RECOMMENDATION = PASS
```

Not set (require actual merge + post-merge seal):

```
D_049_FINAL_ACCEPTANCE = (not yet; requires merge + exact-main verification)
D_049_STATE_CLOSED = NO
POST_MERGE_VERIFIED = NO
```

---

## Lane F / G / H

See:

- `docs/evidence/D-089-OWNER-MERGE-PACKET.md`
- `docs/evidence/D-089-POST-MERGE-SEAL.md`

```
NEXT_ACTION = WAIT FOR EXPLICIT OWNER MERGE AUTHORIZATION FOR #351.
```
