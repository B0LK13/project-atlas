# G-ATLAS-STUDIO-24H — resumable handoff

```text
GOAL                       = G-ATLAS-STUDIO-24H-INTEGRATED-PRODUCT-ADVANCEMENT
GOAL_STATUS                = ACTIVE (not complete)
MERGE_AUTHORIZATION        = NOT_GRANTED
CERTIFIED_A2_PRESERVED     = 2debb7784746228c55503a60e55293929a5f5b1c
```

## Completed this window

| Package | PR | Subject tip | CI | Formal IV |
|---|---|---|---|---|
| AS-STUDIO-A2-002 Mission Journey | #785 | `cd4523fc` (+ docs `c8302bf0`) | **34384775782 SUCCESS** | NOT_STARTED |
| AS-STUDIO-A2-004 Action Evidence | #788 | `4904125f` | **34390223409 SUCCESS** | **PASS** |
| AS-STUDIO-A2-005 Intent Continuity | #788 | `4904125f` | **34390223409 SUCCESS** | **PASS** |

Post-IV tip on #788 may include docs/UX beyond `4904125f` (`441885d4` at last note); those commits are **not** covered by the Formal IV above until re-validated.

### Working user journeys

1. `mission-journey` — open mission → knowledge → development → claim/preview → monitoring + continuity + task-context pointer (#786).
2. `action-evidence` — classify outcomes; forbid auto-retry; optional non-canonical spool.
3. `intent-continuity` — resume after interrupt/stale/duplicate without re-execute.
4. `claim-execute --write-decision` — durable decision file for (2)/(3).

### Ownership to respect

- #786 task-context · #782 target_repo · #781 visual shell · #776 human threads

## Next executable increments

1. Exact-head CI on current #788 tip if claiming post-IV commits.
2. Optional Formal IV extension only if tip diverges materially from `4904125f`.
3. Deeper vault knowledge in journey only if not overlapping #786.
4. Keep certified A2 tip immutable; never merge without authorization.

## Authority reminder

```text
STUDIO_UI != AUTHORITY
FORMAL_IV != MERGE
FORMAL_IV_TIP != LATER_BRANCH_TIP
AUTO_RETRY = FORBIDDEN
```
