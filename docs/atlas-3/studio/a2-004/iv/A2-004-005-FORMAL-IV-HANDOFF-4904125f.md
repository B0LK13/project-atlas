# Formal IV — AS-STUDIO-A2-004 / AS-STUDIO-A2-005

```text
PACKAGES                = AS-STUDIO-A2-004, AS-STUDIO-A2-005
VERDICT                 = PASS
SUBJECT_HEAD            = 4904125f55254023604b228856adb7d23e492a0b
SUBJECT_TREE            = 00734f6352d19f9901e497511b9e51885a74b2c3
CI_EXACT_HEAD           = 34390223409 SUCCESS (exact head match)
VERIFIER                = independent Cursor Formal IV subagent
VERIFIED_AT_UTC         = 2026-09-09T19:06:00Z (approx; session local)
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Scope

Independent adversarial re-check of action-evidence + intent-continuity on the
CI-validated tip only. Later docs/UX tips (`cbf863a9`, `441885d4`, …) are
**not** covered by this verdict unless separately re-validated.

Certified A2 tip `2debb778` remains an untouched ancestor.

## Checks exercised

1. `EXECUTION_FAILED` + `mutation_state=UNKNOWN` → `FAILED_UNCERTAIN`; `auto_retry=false`
2. Spool `authority=false` / `canonical=false`
3. Continuity states; modules never execute/emit
4. Future intents remain `NOT_STARTED` (CI_DISPATCH / IV_REQUEST / …)
5. Journey monitoring/continuity pointers grant no permission
6. Doctor `a2_004_*` / `a2_005_*` PASS
7. Unit tests on subject tip PASS
8. Honesty invariants encoded

## Honesty

```text
CI_PASS != FORMAL_IV
FORMAL_IV != MERGE_AUTHORIZATION
FORMAL_IV_TIP != LATER_BRANCH_TIP
MONITOR != RE-EXECUTE
AUTO_RETRY = FORBIDDEN
```

This verdict does **not** grant merge, promote, deploy, or execution authority.
