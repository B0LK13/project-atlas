# D-074 authentic-estate acceptance matrix (Local D-073 pending)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-FINAL-ACCEPTANCE-074`

This is the ingest gate for Local D-073. It does not invent a Local
result. It does not scan an estate. It does not implement D-042.

```
LOCAL_D073_RESULT = PENDING
D_049_FINAL_ACCEPTANCE = NOT_YET_EVALUATED
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED
D_042_EXECUTION_GATE = CLOSED
REPOSITORY_PRODUCTION_MUTATION = NO
NEW_PR_CREATED = NO
```

Do not collapse technical merge, Windows IV, authentic estate, or
D-049 final acceptance into one score.

## Authoritative technical state (re-read)

```
CURRENT_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
MERGE_COMMIT = 198350319c17b4de0665f972fda0bc51420cd686
PR_348 = MERGED
POST_MERGE_VERIFICATION = PASS
D_049_STATE = POST_MERGE_VERIFIED
SEMANTIC_PRODUCTION_HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
NEW_HIGH = 0
HIGH_OPEN = 0
```

`src/` on `origin/main` equals `ccacaa5`.

## Evidence preservation (verified, do not delete)

```
EVIDENCE_BRANCH = cursor/d049-final-reconciliation-6f85
EVIDENCE_BRANCH_HEAD = 56127d469877df8deaa4cc8eb34743817e53afe0
EVIDENCE_PRESERVATION = YES
```

Unique D-064 / D-066 / D-069 / D-071 / D-072 receipts exist on this
branch and are absent from `main`. Do not merge this branch as a
competing production history.

## Local expected target

```
LOCAL_EXPECTED_TARGET_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
```

## Applicability check (run when Local returns)

1. `git fetch origin main` and record `CURRENT_MAIN`.
2. If `CURRENT_MAIN == 1983503...`:
   `AUTHENTIC_RESULT_TARGET_STALE = NO`
3. If `CURRENT_MAIN` moved: diff `1983503` → current main.
   - production D-049 discovery paths changed →
     `AUTHENTIC_RESULT_TARGET_STALE = YES` → STOP final acceptance
   - docs/evidence/governance only →
     `AUTHENTIC_RESULT_APPLICABLE_TO_CURRENT_MAIN = YES`

```
AUTHENTIC_RESULT_APPLICABILITY_CHECK_READY = YES
```

## Required Local fields (do not pre-fill)

```
TARGET_MAIN =
AUTHORIZED_ROOT_RESOLVED =
UNAUTHORIZED_ROOTS_SCANNED =
PATH_ESCAPES =

SCAN_COMPLETE =
DEPTH_LIMIT_REACHED =
TRUNCATION_CAUSES =

PROJECTS_EXPECTED =
PROJECTS_FOUND =
PROJECT_DISCOVERY_RECALL =

FALSE_PROJECT_MATCH_COUNT =
AMBIGUOUS_MATCH_COUNT =
UNMATCHED_EXPECTED_PROJECT_COUNT =

KNOWLEDGE_EXPECTED =
KNOWLEDGE_FOUND =
KNOWLEDGE_DISCOVERY_RECALL =

FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS =
AMBIGUOUS_KNOWLEDGE_COUNT =

MANUAL_PROJECT_PATHS_REQUIRED =
USER_CORRECTIONS_REQUIRED =
MANUAL_RECLASSIFICATIONS_REQUIRED =

SILENT_IDENTITY_MERGES =
CROSS_PROJECT_LEAKS =
SILENT_KNOWLEDGE_MISASSIGNMENT =

SECRET_CONTENT_ECHO =
CREDENTIAL_ECHO =

DISCOVERY_OUTPUT_UNDERSTANDABLE =
MAJOR_UX_BLOCKER_COUNT =

NEW_HIGH =
HIGH_OPEN =

D049_AUTHENTIC_ESTATE_ACCEPTANCE =
```

## Dimensions (keep separate)

| Dimension | What Local must show |
| --- | --- |
| SAFETY | authorized root only; `PATH_ESCAPES=0`; no secret/credential echo |
| TRUTH / IDENTITY | no silent identity merges; CONNECTED still requires proof |
| PROJECT DISCOVERY | material recall of discoverable projects; no path enumeration |
| KNOWLEDGE DISCOVERY | knowledge found without silent misassignment |
| EXPLAINABILITY | output reasonably understandable; why-matched visible |
| MANUAL BURDEN | owner did not enumerate individual project paths |
| SCAN HONESTY | incompleteness / ambiguity / UNKNOWN stay honest |
| PRODUCT EXPERIENCE | no major UX blocker that voids the product promise |

UNKNOWN is valid when evidence is insufficient. Do not require
artificial 100% recall.

## Miss classification

```
DISCOVERY_DEFECT
HONEST_AMBIGUITY
INSUFFICIENT_EVIDENCE
OWNER_SCOPE_EXCLUSION
GROUND_TRUTH_UNCERTAIN
```

Only `DISCOVERY_DEFECT` counts against product recall.

## Hard gates for CASE A (all required)

1. Real existing owner estate
2. Exact owner-authorized bounded root respected
3. `UNAUTHORIZED_ROOTS_SCANNED = 0`
4. `PATH_ESCAPES = 0`
5. `SILENT_IDENTITY_MERGES = 0`
6. `CROSS_PROJECT_LEAKS = 0`
7. `SILENT_KNOWLEDGE_MISASSIGNMENT = 0`
8. `SECRET_CONTENT_ECHO = 0`
9. `CREDENTIAL_ECHO = 0`
10. `NEW_HIGH = 0`
11. `HIGH_OPEN = 0`
12. Project discovery materially supports the product promise
13. Owner was not required to enumerate individual project paths
14. Scan incompleteness, ambiguity, UNKNOWN remained honest
15. Product output reasonably understandable

## Decision cases (do not apply until Local returns)

### CASE A — Local PASS + all hard gates

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE = PASS
D_049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
```

OPEN means the prerequisite is satisfied. Do not implement D-042.
Do not reopen #344. Do not create a D-042 branch.

### CASE B — Local PARTIAL

Classify residuals as `NON_BLOCKING_PRODUCT_GAPS` or
`ACCEPTANCE_BLOCKERS`.

```
D_049_FINAL_ACCEPTANCE = PARTIAL
D_042_EXECUTION_GATE = CLOSED
```

Smallest evidence-backed next action only. No broad campaign.

### CASE C — Local FAIL

```
D_049_FINAL_ACCEPTANCE = FAIL
D_042_EXECUTION_GATE = CLOSED
```

Classify exact blocking defect(s). Do not fix unless authorized.

## Roadmap only (do not implement)

```
AS-PROJECT-ROADMAP-001 = Atlas Living Project Roadmap
STATUS = ROADMAP_ONLY
```

Belongs after D-049 / D-042 product-flow gates.

## Explicit non-work

No Conversational Capture, Visual Roadmap implementation, Project
Memory, Momentum, Portfolio Intelligence, 2.3, OPT, AutoLab, Prime,
synthetic estate, or new production PR.

```
NEXT_ACTION = WAIT FOR LOCAL D-073 AUTHENTIC-ESTATE RESULT.
```
