# G-ATLAS-STUDIO-24H — resumable handoff

```text
GOAL                       = G-ATLAS-STUDIO-24H-INTEGRATED-PRODUCT-ADVANCEMENT
GOAL_STATUS                = ACTIVE (not complete)
MERGE_AUTHORIZATION        = NOT_GRANTED
CERTIFIED_A2_PRESERVED     = 2debb7784746228c55503a60e55293929a5f5b1c
```

## Completed this window

| Package | PR | Tip | CI | Formal IV |
|---|---|---|---|---|
| AS-STUDIO-A2-002 Mission Journey | #785 | `cd4523fc` | PASS (earlier) | NOT_STARTED |
| AS-STUDIO-A2-004 Action Evidence | #788 | `4904125f` | **34390223409 SUCCESS** | NOT_STARTED |
| AS-STUDIO-A2-005 Intent Continuity | #788 | `4904125f` | **34390223409 SUCCESS** | NOT_STARTED |

### Working user journeys

1. `atlas-studio mission-journey` — open mission → knowledge → development → claim candidates/preview → monitoring + continuity pointers.
2. `atlas-studio action-evidence --decision-file …` — classify outcomes; recovery forbids auto-retry; optional non-canonical spool.
3. `atlas-studio intent-continuity --intent-file … [--decision-file …]` — resume after interrupt/stale/duplicate without re-executing.

### Ownership to respect

- #786 task-context (do not duplicate)
- #782 target_repo binding
- #781 visual shell
- #776 human review threads (do not resolve)

## Next executable increments

1. Formal IV for tip `4904125f` (separate verifier; does not inherit A2-001 IV).
2. Deeper knowledge: vault read lenses into journey when vault+project provided (coordinate with #786).
3. Usability: richer empty/unavailable TUI states; optional decision-file save helper from claim-execute `--json`.
4. Keep certified A2 tip immutable; never merge without authorization.

## Authority reminder

```text
STUDIO_UI != AUTHORITY
PREVIEW != EXECUTION
MONITOR != RE-EXECUTE
AUTO_RETRY = FORBIDDEN
STALE_INTENT != PERMISSION
CI_PASS != FORMAL_IV
FORMAL_IV != MERGE
```
