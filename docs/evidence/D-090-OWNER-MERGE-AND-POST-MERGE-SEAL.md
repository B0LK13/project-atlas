# D-090 — owner-authorized #351 merge and post-merge seal

DIRECTIVE: `D-PROJECT-ATLAS-OWNER-D049-D090-MERGE-AUTHORIZATION`

```
MERGE_AUTHORIZATION = VALID
AUTHORIZED_INTEGRATION_METHOD = GITHUB_MERGE_COMMIT
POST_MERGE_SEAL_EXECUTED = YES
D_049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
D042_IMPLEMENTED = NO
```

This file records the executed owner-authorized merge. It does **not**
implement D-042. `OPEN != IMPLEMENTED`.

---

## Pre-merge fail-closed re-read (before mutation)

```
CURRENT_MAIN                 = 198350319c17b4de0665f972fda0bc51420cd686
PR_351_STATE                 = OPEN
PR_351_MERGED                = NO
PR_351_HEAD                  = 11bf95cba2650db4a1a632915e05ded11421e781
PR_351_TREE                  = 2490d370ee5dc40cdcc4d66e1d821be300ec1c59
PR_351_MERGEABLE             = YES
mergeStateStatus             = CLEAN
D087 ancestor of PR HEAD     = YES
PRODUCTION_SEMANTIC_CHANGES_AFTER_D087_FREEZE = 0
KNOWN_CLOUD_GATES            = PASS (run 31822457411 on 11bf95c)
NEW_HIGH                     = 0
HIGH_OPEN                    = 0
PREMERGE_MAIN_MATCH          = YES
PREMERGE_HEAD_MATCH          = YES
PREMERGE_TREE_MATCH          = YES
```

Ready-for-review transition then re-read: same HEAD / base / MERGEABLE.
`PR_351_READY_TRANSITION = SUCCESS`.

---

## Merge receipt

```
PREVIOUS_MAIN        = 198350319c17b4de0665f972fda0bc51420cd686
AUTHORIZED_PR_HEAD   = 11bf95cba2650db4a1a632915e05ded11421e781
AUTHORIZED_PR_TREE   = 2490d370ee5dc40cdcc4d66e1d821be300ec1c59
MERGE_COMMIT         = c282f2c1eb2dde24f997e480c37d083fda906e54
MERGE_TREE           = 2490d370ee5dc40cdcc4d66e1d821be300ec1c59
PARENT_1             = 198350319c17b4de0665f972fda0bc51420cd686
PARENT_2             = 11bf95cba2650db4a1a632915e05ded11421e781
POST_MERGE_MAIN      = c282f2c1eb2dde24f997e480c37d083fda906e54
PR_351_MERGED        = YES
mergedAt             = 2026-08-14T17:33:22Z
```

`PARENT_1 == PREVIOUS_MAIN`. `PARENT_2 == AUTHORIZED_PR_HEAD`.
`POST_MERGE_MAIN == MERGE_COMMIT`. Merge tree equals authorized PR tree.

---

## Authorized payload on exact POST_MERGE_MAIN

Present on `c282f2c`:

```
D-078  ROOT_MODE_OWNER_AUTHORIZED_VOLUME / owner-authorized-volume
D-080  volume-root scope container + fail-closed knowledge relations
D-083  test_f_linux_filesystem_root_refuses uses Path("/")
D-084  deterministic_hierarchical_fair_v2 + PRESELECT_MULTIPLIER
D-087  estate_path_index.py; canonical_path_key_resolved;
       has_selected_project_ancestor
```

```
AUTHORIZED_PAYLOAD_PRESENT = YES
PRODUCTION_SEMANTIC_DRIFT = 0
UNRELATED_PRODUCTION_CHANGE = 0
```

---

## Exact-main bounded verification (run on c282f2c)

```
D049_FOCUSED     = PASS
D063             = PASS
D064             = PASS
D067             = PASS
D078             = PASS
D080             = PASS
D083             = PASS
D084             = PASS
D087             = PASS
IDENTITY_CONNECT = PASS
SOURCE_LINEAGE   = PASS
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

One pre-existing skip remained in the D-049 focused bundle.

---

## Exact-main GitHub CI (triggered, not manufactured)

Run `31824530391` on head `c282f2c`, conclusion `success`:

| Check name observed | Result |
| --- | --- |
| `ci / control-plane` | success |
| `ci / quality (ubuntu-latest, 3.12, full)` | success |
| `ci / quality (ubuntu-latest, 3.13, compat)` | success |
| `ci / quality (windows-latest, 3.12, windows)` | success |

```
KNOWN_POST_MERGE_CLOUD_GATES = PASS
```

---

## D-049 close

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE = PASS
D_049_STATE = CLOSED
```

Historical authentic receipts remain immutable:

```
198350319 authentic = FAIL
fcaf4f5 authentic = PARTIAL
99aa937 authentic = FAIL
2fcf818 authentic = PARTIAL
b2b5d9b authentic = PASS
```

D-088 Run B documentation lift (not production payload):

```
DOCUMENTATION_LIFT_PROJECT_DISCOVERY = UNCHANGED
DOCUMENTATION_LIFT_KNOWLEDGE_DISCOVERY = IMPROVED
DOCUMENTATION_LIFT_AMBIGUITY = UNCHANGED
DOCUMENTATION_LIFT_EXPLAINABILITY = IMPROVED
DOCUMENTATION_LIFT_AGENT_READINESS = IMPROVED
```

---

## D-042

```
D_042_EXECUTION_GATE = OPEN
D042_IMPLEMENTED = NO
NEXT_ACTION = RETURN TO OWNER FOR FRESH D-042 EXECUTION AUTHORIZATION.
```

Do not reopen `#344`. Do not reuse an old execution branch.
