# AS-STUDIO-A2-006 — evidence

```text
PACKAGE_ID              = AS-STUDIO-A2-006
BRANCH                  = feat/as-studio-a2-006-mission-session
PR                      = PENDING
BASE_BRANCH             = feat/as-studio-a2-004-action-evidence
BASE_FREEZE_HEAD        = 10df59fb0d0241bb8bc117b37df4fd205642ac32
BASE_FREEZE_TREE        = 1e17bddc30cecff2070c2b0b24a4cf57012d0027
FORMAL_IV_PRIOR         = PASS on 4904125f (A2-004/005 only; not inherited)
HEAD                    = PENDING_COMMIT
TREE                    = PENDING_COMMIT
CI_EXACT_HEAD           = PENDING
FORMAL_IV               = NOT_STARTED
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Local validation

```text
Studio unit suite A0–A2 + A2-002/004/005/006: 126 passed
Doctor: a2_006_* checks included
```

## Demonstrated risks

| Case | Coverage |
|---|---|
| Cross-process resume | `test_cross_process_resume` |
| Mismatched intent_id | `test_mismatched_intent_binding` + continuity state |
| Mismatched repository | `test_mismatched_repo_binding` |
| Uncertain mutation | `test_uncertain_and_persistence_failed` |
| Persistence failed after mutation | `test_write_decision_persistence_failure_after_mutation` (exit 3) |
| Task-context unavailable | doctor + session dependencies |

## Honesty

```text
CI_PASS != FORMAL_IV
FORMAL_IV_4904125f != THIS_CANDIDATE
AUTO_RETRY = FORBIDDEN
```
