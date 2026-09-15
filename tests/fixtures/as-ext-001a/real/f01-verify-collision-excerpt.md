# VERIFY / AS-RET Sequencing Decision

status: decided
decision_owner: project-owner
selected_option: 1
decision: formally-close-verify-as-superseded

main_base: d2231d0e8659b9559c0e70bd9f9e58e80042f56b

superseded_branch:
  name: verify/atlas-core-vertical-slice
  head: 04a62feb5de32c4f917ca405f2d46bfe8f56d1e4
  implementation_commits:
    - cfe085e0a8ff6ffa521c97b33d343c06e7949b30
    - 3257bb5b86cb43ec6b5acb576b7986682f849011

superseding_integration:
  merge_commit: a3fdb711dd0b3b1b00b8984482dcb4c1d63e3998
  later_certified_history: 098c5e7ea030d4c52e742e71f45ac10639c66513

verify_disposition:
  status: superseded
  active_work_package: false
  serialization_owner: false
  merge_authorized: false
  historical_evidence_preserved: true
  branch_deletion_authorized: false

as_ret_disposition:
  status: may-proceed-to-governance-rereview
  serialization_conflict_with_verify: resolved
  implementation_changes_authorized: false
  merge_authorized: false

# [...excerpt boundary: source lines 34-57 omitted...]
## Option Disposition

### Option 1 selected

The verify branch is formally closed as superseded by the later
governance-approved AS-CORE-003 integration. It remains immutable historical
evidence, is not an active work package, has no serialization ownership over
`src/project_atlas/ingestion.py`, and is not merge-authorized.

### Option 2 rejected

Leaving the branch silently abandoned would preserve ambiguity and create a
recurring risk that later agents interpret it as active or mergeable.

### Option 3 rejected
