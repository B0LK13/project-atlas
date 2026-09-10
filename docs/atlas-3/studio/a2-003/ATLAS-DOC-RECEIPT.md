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
out_of_tree_evidence:
  # Recorded outside the repository on purpose: appending them to this branch
  # would move the head and invalidate the pending exact-head CI run.
  - ~/Projects/atlas-handoffs/A2-003-LIVE-DEMONSTRATION-2026-09-09.md
  - ~/Projects/atlas-handoffs/INTEGRATION-CANDIDATE-001.md
  - ~/Projects/atlas-handoffs/INTEGRATION-SEQUENCE-AND-OWNER-ACTIONS.md
  - ~/Projects/atlas-handoffs/OWNER-DECISION-PACKET-2026-09-09.md
  - ~/Projects/atlas-handoffs/ATLAS-REMAINING-WORK-MAP-2026-09-09.md
  - ~/Projects/atlas-handoffs/CORRECTIONS-AND-DEPENDENCY-BOUNDARIES.md
  - ~/Projects/atlas-handoffs/INTEGRATION-SEQUENCE-AND-OWNER-ACTIONS.md
  - ~/Projects/atlas-handoffs/atlas-integration-rehearse.sh  (executable rehearsal, runs the repo's own gates)
validation:
  studio_suite: 148 passed
  package_tests: 47
  ruff: clean by explicit file path (repo config excludes scripts/, issue #774)
  doctor: ok, includes a2_003_task_context
  integration_candidate:
    base: origin/main b87b4a22
    candidate: 2cd379f2 (tree 326625a1)
    conflicts: WORKLOG.md only, resolved by union
    full_repository_suite: pytest exit 0, no test failed
  exact_head_ci:
    - head: 924a4f88, run: 34386646378, conclusion: success
    - head: e0f50f69, run: 34390138198, conclusion: success
    - head: 2f89b26e, run: 34394357024, conclusion: success
    - head: 19aa31b6, run: superseded (cancelled by the next push)
    - head: 054ca32c, run: 34399234573, conclusion: success
sync_state: not_run
blockers:
  - "Vault/mda-cli normalization NOT run; this receipt covers raw in-repo docs only and claims no vault sync"
  - "FORMAL_IV NOT_STARTED; atlas-dag gate 786 reports FORMAL_IV_MISSING"
  - "CLAIM_INTEGRITY_NOT_PASS:UNKNOWN - the lane was never claimed through the control plane"
  - "MERGE_AUTHORIZATION = NOT_GRANTED"
```

Session notes:
- Surface is CLI + schema + Python API. **No Studio UI integration.** Browser
  verification was not performed; visual behaviour is unverified.
- Certified object `2debb778` (#776) untouched. #781, #785 and #788 belong to
  other agents and were not edited; #785's advance was consumed by merging its
  tip into this branch (`19aa31b6`), which is why this head supersedes the
  CI-green `2f89b26e`.
- Three defects were found by running the real entry point: two baseline
  (reproduced on base `cd4523fc` through the pre-existing claim path) and one in
  this package's lens classifier. A fourth, in the first cut of continuation
  verification, was found by live use.
