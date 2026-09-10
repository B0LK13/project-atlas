# AS-STUDIO-A2-004 — first work package

```text
PACKAGE_ID                         = AS-STUDIO-A2-004
TITLE                              = Action evidence + recovery (monitor results)
BASE                               = feat/as-studio-a2-002-mission-journey @ cd4523fc
BRANCH                             = feat/as-studio-a2-004-action-evidence
DEPENDS_ON_UNMERGED_A2_STACK       = YES (A2-001 + A2-002 disclosed)
OVERLAP_AVOIDANCE                  = does not take over #786 task-context;
                                     does not touch #782 target_repo binding;
                                     does not take over #781 visual shell
MUTATION_SURFACE                   = NONE for control plane;
                                     optional non-canonical spool write only
FORMAL_IV                          = NOT_STARTED
MERGE_AUTHORIZATION                = NOT_GRANTED
```

## Selected user journey

> After a governed claim evaluate/execute (or refusal/failure), a user
> inspects durable decision evidence, understands whether the outcome is
> confirmed success, refusal, dry-run, pending execute, or uncertain failure,
> sees recovery steps that preserve evidence and forbid auto-retry, and may
> spool the packet into the knowledge-capture path without promoting authority.

```text
claim-evaluate / claim-execute decision JSON
  → action-evidence classification + recovery
  → optional knowledge spool (CAPTURE!=AUTHORITY)
  → refresh mission-journey / mission-control (human/agent)
```

## Why this slice

- Goal outcome: *monitor their results, and recover from failures without
  losing context* — complementary to A2-002 (open/inspect) and #786
  (task-context preparation).
- Completes the governed lifecycle surface: intent → preview → evaluate →
  execute-or-refuse → **evidence** without granting new permissions.

## Reuse

| Concern | Source |
|---|---|
| Decision schema / honesty | `ATLAS_STUDIO_ACTION_DECISION_V1` / A2-001 |
| Mission refresh | `mission-journey` / `mission-control` |
| Knowledge feed | non-canonical spool → existing quarantine/normalize path later |
| No parallel orchestration | does not emit OWNER_CLAIMED or call governance execute |

## Non-goals

- Auto-retry of claim-execute.
- Treating uncertain mutation as no-op success.
- CI_DISPATCH / IV_REQUEST / HANDOFF / STEAL / MERGE / WORKTREE.
- Taking over #786 task-context implementation.
- Promoting spool contents to Truth Core / Layer B.

## Acceptance criteria

1. `atlas-studio action-evidence --decision-file … --json` emits
   `ATLAS_STUDIO_ACTION_EVIDENCE_V1` that validates.
2. `EXECUTION_FAILED` + `mutation_state=UNKNOWN` → `FAILED_UNCERTAIN` and
   `recovery.auto_retry=false` with inspect-before-retry guidance.
3. Confirmed `EXECUTED`+`mutated=true` → `CONFIRMED_SUCCESS`.
4. Missing decision file → `UNAVAILABLE` (not fabricated success).
5. `--write-spool` writes authority=false / canonical=false envelope only when
   `--spool-dir` is provided.
6. Doctor checks `a2_004_*` pass.
7. Unit tests cover success, uncertain failure, refusal, pending, dry-run,
   unavailable, spool paths.
8. Certified A2 tip `2debb778` is not mutated.
