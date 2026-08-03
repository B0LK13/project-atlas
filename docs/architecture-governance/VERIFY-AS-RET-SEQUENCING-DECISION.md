# VERIFY / AS-RET Sequencing Decision

status: decided
decision_owner: project-owner
selected_option: 2
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

## Rationale

This disposition is based on repository history, structural comparison,
merge-tree evidence, and the later governance-approved integration.

It does not rewrite or invalidate historical verify evidence. It changes
the branch's operational status from potentially active to superseded.

The two branches represent independently developed implementations of
substantially overlapping AS-CORE-003 functionality, not a small continuation:

- verify work was created earlier on August 2, 2026 (`cfe085e0...`, `3257bb5b...`);
- a later implementation followed a separate governance process and was merged at
  `a3fdb711dd0b3b1b00b8984482dcb4c1d63e3998`;
- later certified history continued on top of that integration (`098c5e7...`);
- verify lacks durable source lineage, lifecycle receipts, project identity
  locking, source identity, and related governed components present in the later
  integrated lineage;
- both sides independently created overlapping compiler and schema files;
- merge-tree reports add/add conflicts for independently created files;
- verify is therefore classified as an incomplete first pass;
- no behavior from verify is authorized for implicit inclusion in AS-RET-001.

## Option Disposition

### Option 1 rejected

Leaving the branch silently abandoned would preserve ambiguity and create a
recurring risk that later agents interpret it as active or mergeable.

### Option 3 rejected

The repository evidence is sufficiently strong to make an owner decision without
waiting for unavailable historical intent:

- the later implementation is materially more complete;
- it passed governance;
- it was merged;
- subsequent work was built on top of it;
- the earlier branch remained unmerged.

If contrary evidence later emerges, the owner decision may be reopened through
architecture governance. Until then, the verify branch is superseded.
