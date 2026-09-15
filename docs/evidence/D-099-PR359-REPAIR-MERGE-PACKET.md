# D-099 — PR #359 repair-merge owner packet

```
DIRECTIVE = D-PROJECT-ATLAS-CLOUD-D099-PR359-EXACT-MAIN-CI-UNBLOCK-READINESS
AUTHORIZED_PR_CANDIDATE = 359
MERGE_AUTHORIZATION = NOT_GRANTED
OWNER_EXCEPTION_REQUIRED = YES
PR359_MERGED = NO
CURRENT_MAIN_IS_RED = YES
```

This is an exception **proposal**, not authorization.
`CERTIFIED != AUTHORIZED`. `REPAIR_READY != MERGED`.
`PR_GREEN != POST_MERGE_MAIN_GREEN`.

---

## Exact pins

```
EXPECTED_PARENT_MAIN = 689f740f6ebe1bd8c2f5be956235369c924021dc
EXPECTED_PARENT_MAIN_TREE = 0ffbda2803237c2d862771b5c0bc710e700aad48
CANDIDATE_PR_HEAD = <set after final push>
CANDIDATE_PR_TREE = <set after final push>
MERGE_METHOD = GitHub merge commit
SQUASH = NO
REBASE = NO
FORCE_PUSH = NO
```

Refresh commit parents (merge, not rebase):

```
PARENT_1 = ca606e51d74cc1390e5b9b72ce8e1b4cdbca6454
PARENT_2 = 689f740f6ebe1bd8c2f5be956235369c924021dc
```

---

## Why this is a controlled repair candidate

```
RED_CAUSE = external stub drift exposing version-sensitive type-ignore
FAILURE_INTRODUCED_BY_360 = NO
FAILURE_CAUSE = DEPENDENCY_STUB_DRIFT
FAILURE_SURFACE = src/project_atlas/yaml_structured.py
FAILURE_SEMANTIC_RUNTIME_DEFECT = NO
FAILURE_TYPECHECK_COMPATIBILITY_DEFECT = YES
PR359_FIXES_EXACT_RED_CAUSE = YES
PR359_FEATURE_SCOPE_ALREADY_CERTIFIED = YES
PR359_REFRESHED_AGAINST_CURRENT_MAIN = YES
PR359_YAML_CLOSER_PRESENT = YES
DUPLICATE_FIX_REQUIRED = NO
```

Exact-main CI `31872306418` FAIL: ubuntu-full mypy unused-ignore at
`yaml_structured.py:222` under mypy 2.3.1 + types-PyYAML 6.0.12.20260815.
`#360` changed only WORKLOG/docs/evidence. yaml on `9441b0c` equals yaml
on `689f740`.

`#359` already contains:

```
closer: Any = loader.dispose
closer()
```

No dependency pin. No unused-ignore disable. No YAML runtime change.

---

## A/B proof (this machine, matching CI versions)

```
BASE_REPRODUCER = PASS_REPRODUCED_FAILURE
  worktree 689f740 + mypy 2.3.1 + types-PyYAML 6.0.12.20260815
  → yaml_structured.py:222 unused-ignore

FIXED_REPRODUCER = PASS
  refreshed #359 + same toolchain
  → Success: no issues found in 187 source files
```

---

## Validation on refreshed #359

```
CONTEXT_WEB_TESTS = PASS
CONTEXT_HANDOFF_TESTS = PASS
YAML_RUNTIME_REGRESSION = PASS (tests/unit/test_yaml_structured.py)
RENDERER_GATE = PASS
RUFF = PASS
MYPY = PASS
WEB_TYPECHECK = PASS
WEB_BUILD = PASS (72 modules; #359 scope, not five-PR compose)
NEW_HIGH = 0
NEW_MEDIUM = 0
```

GitHub CI on the refreshed tip is recorded after push. Do not treat this
packet as complete until `PR359_CI = PASS` is observed.

---

## Queue effect

```
QUEUE_ORDER_BASE = 359 → 358 → 356 → 357 → 354
QUEUE_ORDER_REPROVED = YES
PR354_SPECIAL_HOLD = YES
PR354_SPECIAL_HOLD_REASON = LOCAL AUTHENTIC WEB IV PARTIAL / ProdNav project-context loss
PR354_LOCAL_AUTHENTIC_IV = PARTIAL
```

After an owner-authorized `#359` merge, require:

```
POST_MERGE_MAIN_CI = PASS
```

before `#358` is considered. D-099 authorizes none of `#358`/`#356`/`#357`/`#354`.

---

## Hygiene

```
PR_352_DISPOSITION = CLOSE WITHOUT MERGE
PR_355_DISPOSITION = SUPERSEDED BY #360 / D-096 — DO NOT MERGE
NEW_PRODUCTION_PR_CREATED = 0
```

---

## Owner actions required

1. Review this packet and refreshed `#359`.
2. If desired, grant a **separate** exception authorization for `#359` only
   as first integration slice + current-main CI repair.
3. Merge with a GitHub merge commit. Cloud will not infer authorization.
4. Wait for post-merge main CI PASS before any later queue PR.
