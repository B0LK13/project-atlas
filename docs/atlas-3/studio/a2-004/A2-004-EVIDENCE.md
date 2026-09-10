# AS-STUDIO-A2-004 / A2-005 — evidence

```text
PACKAGE_IDS             = AS-STUDIO-A2-004, AS-STUDIO-A2-005
BRANCH                  = feat/as-studio-a2-004-action-evidence
PR                      = #788
BASE_BRANCH             = feat/as-studio-a2-002-mission-journey
BASE_HEAD               = cd4523fc588ac941b13ad75731624039e572ba71
CERTIFIED_A2_PRESERVED  = 2debb7784746228c55503a60e55293929a5f5b1c
FORMAL_IV_SUBJECT_HEAD  = 4904125f55254023604b228856adb7d23e492a0b
FORMAL_IV_SUBJECT_TREE  = 00734f6352d19f9901e497511b9e51885a74b2c3
CI_EXACT_HEAD           = 34390223409 SUCCESS
FORMAL_IV               = PASS (see iv/A2-004-005-FORMAL-IV-HANDOFF-4904125f.md)
BRANCH_TIP              = 441885d4b8ecb4cbde771d5de796c95448e6461f
TIP_NOTE                = tip includes post-IV docs/UX; Formal IV does not auto-extend
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Local validation (subject tip)

```text
Studio A2-004/005 unit tests: 15 passed (Formal IV environment)
Doctor: a2_004_* + a2_005_* PASS
```

## Exact-head CI (Formal IV subject)

```text
run    = https://github.com/B0LK13/project-atlas/actions/runs/34390223409
head   = 4904125f55254023604b228856adb7d23e492a0b
result = SUCCESS
```

## Honesty

```text
CI_PASS != FORMAL_IV
FORMAL_IV != MERGE_AUTHORIZATION
FORMAL_IV_TIP != LATER_BRANCH_TIP
IMPLEMENTED_IN_LANE != MERGED
AUTO_RETRY = FORBIDDEN
```
