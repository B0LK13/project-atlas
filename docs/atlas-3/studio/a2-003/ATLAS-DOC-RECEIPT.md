ATLAS-DOC-RECEIPT

```yaml
event_id: ASE-STUDIO-A2-003-20260909-TASK-CONTEXT
raw_event: docs/atlas-3/studio/a2-003/A2-003-EVIDENCE.md
normalized_event: not_run
atlas_updates:
  - docs/atlas-3/studio/a2-003/README.md
  - docs/atlas-3/studio/a2-003/A2-003-FIRST-WORK-PACKAGE.md
  - docs/atlas-3/studio/a2-003/A2-003-EVIDENCE.md
  - docs/atlas-3/studio/a2-003/ATLAS-DOC-RECEIPT.md
  - docs/atlas-3/studio/README.md
  - WORKLOG.md
validation:
  studio_suite: 148 passed (A0 + A1 + A1-semantic + A2 + A2-002 + A2-003)
  package_tests: 47
  ruff: clean by explicit file path (repo config excludes scripts/, issue #774)
  doctor: ok, includes a2_003_task_context
  exact_head_ci:
    - head: 924a4f88, run: 34386646378, conclusion: success (4/4)
    - head: e0f50f69, run: 34390138198, conclusion: success (4/4)
    - head: b3fbcb51, run: pending at receipt time
sync_state: not_run
blockers:
  - "Vault/mda-cli normalization NOT run in this session; this receipt records raw in-repo docs only"
  - "Formal IV for A2-003 NOT_STARTED; atlas-dag gate 786 reports FORMAL_IV_MISSING"
  - "CLAIM_INTEGRITY_NOT_PASS:UNKNOWN — the lane was never claimed through the control plane"
  - "MERGE_AUTHORIZATION = NOT_GRANTED"
```

Session notes:
- Certified object `2debb778` (#776) untouched; no commit on any branch owned
  elsewhere (#781, #785 both advanced during the session and were not edited).
- Package surface is CLI + schema + Python API. **No Studio UI integration.**
- Two baseline defects in the live Studio path were reproduced on base
  `cd4523fc` and repaired in the shared `_live_frontier` helper; a third, in
  this package's lens classifier, was found by running the real lenses over a
  real vault.
- Read-only evidence: a real `atlas init` vault (30 files, plus seeded decision
  and conflict records) is byte-identical before and after every exercised run.
  This covers the paths exercised; it is not a proof that all paths are
  mutation-free.
