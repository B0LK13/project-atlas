# AS-STUDIO-A2-004 / A2-005 — evidence

```text
PACKAGE_IDS             = AS-STUDIO-A2-004, AS-STUDIO-A2-005
BRANCH                  = feat/as-studio-a2-004-action-evidence
PR                      = #788
BASE_BRANCH             = feat/as-studio-a2-002-mission-journey
BASE_HEAD               = cd4523fc588ac941b13ad75731624039e572ba71
CERTIFIED_A2_PRESERVED  = 2debb7784746228c55503a60e55293929a5f5b1c
HEAD                    = 4904125f55254023604b228856adb7d23e492a0b
TREE                    = 00734f6352d19f9901e497511b9e51885a74b2c3
CI_EXACT_HEAD           = 34390223409 SUCCESS
FORMAL_IV               = NOT_STARTED
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Local validation

```text
Studio unit suite: 116 passed
Doctor: a2_004_* + a2_005_* PASS
```

## Exact-head CI

```text
run    = https://github.com/B0LK13/project-atlas/actions/runs/34390223409
head   = 4904125f55254023604b228856adb7d23e492a0b
result = SUCCESS (ubuntu 3.12 full, ubuntu 3.13 compat, windows 3.12, control-plane)
```

## Honesty

```text
CI_PASS != FORMAL_IV
FORMAL_IV != MERGE_AUTHORIZATION
IMPLEMENTED_IN_LANE != MERGED
AUTO_RETRY = FORBIDDEN
MONITOR != RE-EXECUTE
STALE_INTENT != PERMISSION
```

Note: subsequent docs-only tip commits may move HEAD; treat `CI_EXACT_HEAD`
above as the validated implementation tip unless a newer exact-head run is
recorded.
