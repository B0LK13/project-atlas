ATLAS-DOC-RECEIPT

```yaml
event_id: AE-AS-IMPR-PLANE-001-20260910
goal_id: ATLAS-EVIDENCE-TO-IMPROVEMENT-20260910
raw_event: docs/evidence/AS-IMPR-PLANE-001-DOC-RECEIPT.md
normalized_event: pending
atlas_updates:
  - src/project_atlas/improvement_plane/
  - tests/unit/test_as_impr_plane_001.py
  - docs/AS-IMPR-PLANE-001.md
  - docs/evidence/AS-IMPR-PLANE-001-SOURCE-PIN.json
validation: passed
sync_state: pending
blockers:
  - atlas_agent_adapters_fail_doctor
  - MERGE_AUTHORIZATION_NOT_GRANTED
  - CI_NOT_RUN_FOR_THIS_LANE
  - INDEPENDENT_VERIFICATION_NOT_CLAIMED
  - CANONICAL_VAULT_SYNC_NOT_PERFORMED
identity_correction: >
  Prior handoff incorrectly listed candidate_head/tree as equal to the
  source pin while implementation existed only as untracked working-tree
  files. Source pin remains the analysis baseline; candidate identity is
  the implementation commit after checkpoint (see git log), not the pin.
directive: ATLAS-PARALLEL-IMPROVEMENT-PLANE-20260910
package_id: AS-IMPR-PLANE-001
worktree: /home/gebruiker/Projects/project-atlas-worktrees/improvement-plane
branch: feat/as-impr-plane-001-delivery-evidence-report
source_pin_head: b87b4a226f4aa8b2f669edf112aa3476454f754f
source_pin_tree: 46d1989b026a2f15920ec5e1c78a106799bd1249
candidate_head: PENDING_CHECKPOINT_COMMIT
candidate_tree: PENDING_CHECKPOINT_COMMIT
working_tree_at_receipt_draft: dirty_untracked_implementation
focused_tests: tests/unit/test_as_impr_plane_001.py
claims:
  merge: false
  independent_verification: false
  ci_green_for_lane: false
  measured_productivity_gain: false
  recommendation_authority: false
  source_evidence_mutated: false
  baseline_ci_covers_new_code: false
summary: >
  Initial read-only improvement report capability (AS-IMPR-PLANE-001)
  ready for checkpoint commit. Generated demo reports are regenerable
  and must not self-ingest as delivery evidence.
```
