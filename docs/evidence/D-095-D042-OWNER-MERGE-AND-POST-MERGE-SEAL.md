# D-095 — owner-authorized #353 merge and post-merge seal

DIRECTIVE: `D-PROJECT-ATLAS-OWNER-D042-D095-MERGE-AND-CLOSE`

```
MERGE_AUTHORIZATION = VALID
AUTHORIZED_INTEGRATION_METHOD = GITHUB_MERGE_COMMIT
POST_MERGE_SEAL_EXECUTED = YES
D042_STATE = CLOSED
D042_FINAL_ACCEPTANCE = PASS
CONVERSATIONAL_CAPTURE = PRODUCTION_ACCEPTED
LOCAL_D042_CAMPAIGN_STATE = SEALED_PASS
ROADMAP_PR_354_TOUCHED = NO
NEW_FEATURE_WORK_STARTED = NO
```

This file records the executed owner-authorized merge of PR `#353`.
It does **not** start Roadmap `#354`, Memory, Momentum, incremental
connect, Atlas 2.3, OPT, transcript extraction, or MCP write capture.

Cloud did **not** directly observe Windows Local evidence. Owner-supplied
Local receipts remain owner-supplied. D-092B remains supplemental
controlled routing coverage only — not authentic owner / pilot / estate
evidence.

---

## Pre-merge fail-closed re-read (before mutation)

```
CURRENT_MAIN                 = c282f2c1eb2dde24f997e480c37d083fda906e54
PR_353_STATE                 = OPEN
PR_353_MERGED                = NO
PR_353_DRAFT                 = YES
PR_353_HEAD                  = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
PR_353_TREE                  = ed78a92e941d88ac1aa198c311b0120b4c9ce7ef
PR_353_MERGEABLE             = YES
mergeStateStatus             = CLEAN
reviews                      = []
reviewThreads                = []
D091 ancestor of PR HEAD     = YES
D091_FREEZE_DESCENDS_FROM_AUTHORIZED_MAIN = YES
PR_HEAD_DESCENDS_FROM_D091_FREEZE = YES
PRODUCTION_SEMANTIC_CHANGES_AFTER_D091_FREEZE = 0
UNRELATED_PRODUCTION_CHANGE  = 0
FINAL_HEAD_CI                = PASS (run 31837034472 on 822a6d8)
NEW_SECURITY_HIGH            = 0
NEW_HIGH                     = 0
HIGH_OPEN                    = 0
PREMERGE_MAIN_MATCH          = YES
PREMERGE_HEAD_MATCH          = YES
PREMERGE_TREE_MATCH          = YES
```

Observed final-head CI jobs on `822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb`,
run `31837034472`, conclusion `success`:

| Check name observed | Result |
| --- | --- |
| `ci / control-plane` | success |
| `ci / quality (ubuntu-latest, 3.12, full)` | success |
| `ci / quality (ubuntu-latest, 3.13, compat)` | success |
| `ci / quality (windows-latest, 3.12, windows)` | success |

Ready-for-review transition then immediate re-read: same HEAD / TREE /
BASE / MERGEABLE. `PR_353_READY_TRANSITION = SUCCESS`.
`REVIEW_CONVERSATIONS_CLEAR = YES` (no threads existed; none fabricated).

---

## Merge receipt

Obtained only after GitHub confirmed `state=MERGED`. The pre-merge
computed `merge_commit_sha` was not used as the receipt.

```
PREVIOUS_MAIN        = c282f2c1eb2dde24f997e480c37d083fda906e54
AUTHORIZED_PR_HEAD   = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
AUTHORIZED_PR_TREE   = ed78a92e941d88ac1aa198c311b0120b4c9ce7ef
MERGE_COMMIT         = 9441b0c576dc54bc43a92a62a4e972889424c21f
MERGE_TREE           = ed78a92e941d88ac1aa198c311b0120b4c9ce7ef
PARENT_1             = c282f2c1eb2dde24f997e480c37d083fda906e54
PARENT_2             = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
POST_MERGE_MAIN      = 9441b0c576dc54bc43a92a62a4e972889424c21f
PR_353_MERGED        = YES
MERGED_AT            = 2026-08-14T20:36:07Z
```

Lineage hard gate:

```
PARENT_1 == AUTHORIZED_BASE_MAIN = YES
PARENT_2 == AUTHORIZED_PR_HEAD   = YES
MERGE_TREE == AUTHORIZED_PR_TREE = YES
POST_MERGE_MAIN == MERGE_COMMIT  = YES
POST_MERGE_VERIFICATION          = PASS
```

---

## Authorized payload on exact POST_MERGE_MAIN

Present on detached `9441b0c` (tree `ed78a92`):

```
atlas.conversation-capture.v1          YES
atlas capture conversation             YES
POST /v1/captures/conversation         YES
Knowledge Inbox projection             YES
Web Knowledge capture display          YES
agent context non-authoritative label  YES
raw transcript persisted by default    NO
capture auto-promotions                0
Truth Core capture mutations           0
project identities minted by capture   0
discovery side effects                 0
connect side effects                   0
ingest side effects                    0
```

```
AUTHORIZED_PAYLOAD_PRESENT = YES
PRODUCTION_SEMANTIC_DRIFT = 0
UNRELATED_PRODUCTION_CHANGE = 0
```

Production freeze remains `9ec65c7662f1ed8e18805a9496df8ded19d2c65e`
(tree `97e56303ec7642bb86c9799cd2dbd79bfa1eaf08`). Paths after that
freeze on `#353` are evidence/governance only.

---

## Exact-main bounded verification (detached 9441b0c)

Not branch tip. Not old PR worktree. Interpreter:
`/workspace/.venv/bin/python` (editable `src/project_atlas`).

```
D042_FOCUSED     = PASS
D049_REGRESSION  = PASS
SESSION_CAPTURE  = PASS
KNOWLEDGE_INBOX  = PASS
AGENT_CONTEXT    = PASS
IDENTITY_CONNECT = PASS
SOURCE_LINEAGE   = PASS
API              = PASS
CONTROL_PLANE    = PASS
RUFF             = PASS
MYPY             = PASS
WEB_TYPECHECK    = PASS
WEB_BUILD        = PASS
NEW_SECURITY_HIGH = 0
NEW_HIGH         = 0
HIGH_OPEN        = 0
POST_MERGE_VERIFICATION = PASS
```

Focused pytest (D-042 + D-049 063/064/067/078 + connect + source
identity + handoff + session capture + inbox + API ADV + SEC-009 + MCP):
140 passed, 1 pre-existing skip, exit 0.

Control plane: `pytest atlas-vault-documentation/tests --no-cov`
171 passed, exit 0.

```
ruff check .     All checks passed
mypy src         Success: no issues found in 187 source files
apps/web tsc -b  exit 0
apps/web vite build  exit 0 (70 modules)
```

Historical `AS-CODER-ALPHA-044-HIGH` backlog row is a separate package
and is not a D-042 open HIGH.

---

## Exact-main GitHub CI (triggered, not manufactured)

Run `31838651156` on head `9441b0c576dc54bc43a92a62a4e972889424c21f`,
event `push`, conclusion `success`:

| Check name observed | Result |
| --- | --- |
| `ci / control-plane` | success |
| `ci / quality (ubuntu-latest, 3.12, full)` | success |
| `ci / quality (ubuntu-latest, 3.13, compat)` | success |
| `ci / quality (windows-latest, 3.12, windows)` | success |

```
EXACT_MAIN_GITHUB_CI = PASS
EXACT_MAIN_CI_RUN    = 31838651156
```

---

## Owner-supplied Local (Cloud-unobserved)

Do not treat the following as Cloud-observed Windows evidence:

```
PROJECT_ID = dark-factory-02ee94d0
PROJECT_UUID = c440d169-bb43-4e97-a175-0d3f62177d8f
UUID_OWNER_CARDINALITY = 1
IDENTITY_CROSS_SURFACE_MATCH = PASS
GOVERNED_VAULT_HEALTH = PASS
D092_CAPTURE_MUTATED_CANONICAL_VAULT = NO
D092B_MUTATED_CANONICAL_VAULT = NO
DOGFOOD_BASELINE_READY = YES
DOGFOOD_SNAPSHOT = CREATED
D091_LOCAL_ACCEPTANCE = PASS
D092A_ONBOARDING = PASS
D092_AUTHENTIC_OWNER_ROUND_TRIP = PASS
D092B_ROUTING_SUPPLEMENT = PASS
D092_RECONCILED_RESULT = PASS
LOCAL_D042_CAMPAIGN_STATE = SEALED_PASS
```

D-092B is supplemental controlled routing coverage only.

---

## D-042 close

```
D042_FINAL_ACCEPTANCE = PASS
D042_STATE = CLOSED
CONVERSATIONAL_CAPTURE = PRODUCTION_ACCEPTED
LOCAL_D042_CAMPAIGN_STATE = SEALED_PASS
```

`PRODUCTION_ACCEPTED` means the authorized `#353` payload is on `main`
at merge commit `9441b0c`. It does **not** mean:

```
AUTHENTIC_PILOT = PASS
EXTERNAL_SECURITY_CERTIFICATION = PASS
COMMERCIAL_GA = YES
CODEX_VALIDATED = YES
```

---

## Evidence-only seal vs merge receipt

This D-095 commit is evidence/governance only. If it later lands on
`main`, do not confuse the evidence-tip SHA with the merge receipt.

```
D042_MERGE_COMMIT      = 9441b0c576dc54bc43a92a62a4e972889424c21f
FINAL_MAIN_AFTER_SEAL  = 9441b0c576dc54bc43a92a62a4e972889424c21f
```

`FINAL_MAIN_AFTER_SEAL` equals the merge commit while this seal remains
off `main`. Update that field only after an evidence-only follow-up
lands.

---

## Explicit non-actions

```
ROADMAP_PR_354_TOUCHED = NO
NEW_FEATURE_WORK_STARTED = NO
NEXT_ACTION = D-042 CLOSED. RETURN TO OWNER. STOP.
```
