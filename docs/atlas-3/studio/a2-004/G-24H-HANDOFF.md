# G-ATLAS-STUDIO-24H — resumable handoff

```text
GOAL                       = G-ATLAS-STUDIO-24H-INTEGRATED-PRODUCT-ADVANCEMENT
GOAL_STATUS                = ACTIVE (not complete)
MERGE_AUTHORIZATION        = NOT_GRANTED
CERTIFIED_A2_PRESERVED     = 2debb7784746228c55503a60e55293929a5f5b1c
```

## Completed this window (so far)

| Package | PR | Tip | Status |
|---|---|---|---|
| AS-STUDIO-A2-002 Mission Journey | #785 | `cd4523fc` | CI PASS earlier; Formal IV NOT_STARTED |
| AS-STUDIO-A2-004 Action Evidence | #788 | `d5b060d5` | CI in progress run `34388278290`; Formal IV NOT_STARTED |

### Working user journeys

1. `atlas-studio mission-journey` — open mission → knowledge states → development context → claim candidates/preview → monitoring pointer.
2. `atlas-studio action-evidence --decision-file …` — classify outcomes; recovery forbids auto-retry; optional non-canonical spool.

### Ownership to respect

- #786 task-context (do not duplicate)
- #782 target_repo binding (do not take over)
- #781 visual shell (do not take over)
- #776 human review threads (do not resolve)

## Next executable increments (pick unowned)

1. After CI green on #788: update `A2-004-EVIDENCE.md` `CI_EXACT_HEAD`; request Formal IV (separate verifier).
2. Resilience: interrupted-session / duplicate-submission detection for claim intents (idempotent inspect; no auto-retry).
3. Deeper knowledge: wire vault read lenses into journey when vault+project provided (without parallel store; coordinate with #786).
4. UI/usability: honest empty/unavailable states in TUI for journey+evidence (keyboard-friendly CLI already).

## Authority reminder

```text
STUDIO_UI != AUTHORITY
PREVIEW != EXECUTION
MONITOR != RE-EXECUTE
AUTO_RETRY = FORBIDDEN
CI_PASS != FORMAL_IV
FORMAL_IV != MERGE
```
