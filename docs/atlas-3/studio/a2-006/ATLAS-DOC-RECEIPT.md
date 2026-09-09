# ATLAS-DOC-RECEIPT — A2-006 overnight continuation

```text
PACKAGE                 = AS-STUDIO-A2-006
DIRECTIVE               = ATLAS-STUDIO-OVERNIGHT-CONTINUATION-001
DOC_WRITES              = OVERNIGHT-HANDOFF.md, REMAINING-WORK.md, ACCEPTANCE-DEMO.md, this receipt
CODE_WRITES             = snapshot_load.py; continuity/evidence/session/cli; --strict-schema;
                          claim _load_intent_file via snapshot; suite restore after empty tip
MERGE_AUTHORIZATION     = NOT_GRANTED
FORMAL_IV               = NOT_STARTED
CI_EXACT_HEAD_SUCCESS   = NOT_ESTABLISHED (dependency recorded; do not poll-loop)
AUTO_RETRY              = false
SESSION_NE_EXECUTE      = true
INPUT_BYTE_HASH         = parsed-bytes provenance only (not multi-file FS snapshot)
POWER_LOSS_DURABILITY   = NOT claimed by process tests
TASK_CONTEXT_786        = UNAVAILABLE
OBSERVATION_API         = UNAVAILABLE
BRANCH                  = feat/as-studio-a2-006-mission-session
PR                      = https://github.com/B0LK13/project-atlas/pull/791
```

Tip SHA: record from `git rev-parse HEAD` at push time; do not docs-only retip.
