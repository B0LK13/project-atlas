ATLAS-DOC-RECEIPT

```yaml
schema_version: 1
receipt_type: atlas-work-package-certification
work_package_id: AS-WP-004
status: certified
event_id: not-applicable
raw_event: not-required
normalized_event: not-required
stage_1:
  project: project-atlas
  regression_status: passed
  documents_discovered: 8
  documents_routed: 5
  sensitive: 1
  unsupported: 1
  graphify_deferred: 1
stage_2:
  fixtures:
    documentation_rich: passed
    sparse_readme: passed
    monorepo: passed
    mixed_formats: passed
    graphify_present: passed
incremental:
  no_op_replay: passed
  new_document: passed
  changed_document: passed
  deleted_document: passed
  rename_detection: passed
  failed_transaction_retry: passed
performance:
  benchmark_status: passed
  environment: "Python 3.12.3; Linux WSL2 x86_64; /tmp filesystem; mock normalization"
  small_median_seconds: 0.00326
  medium_median_seconds: 0.07426
  large_median_seconds: 0.35855
  no_op_median_seconds: 0.36087
validation:
  focused_tests: 10
  subproject_tests: 129
  parent_tests: 54
  ruff: passed
  mypy: passed
  compilation: passed
  strict_ingestion_validation: passed
graphify:
  inventory: enabled
  semantic_ingestion: deferred
  authority: derived
atlas_updates:
  - atlas-vault-documentation/internal/project_discovery.py
  - atlas-vault-documentation/internal/document_inventory.py
  - atlas-vault-documentation/internal/ingestion_state.py
  - atlas-vault-documentation/internal/ingestion_orchestrator.py
  - atlas-vault-documentation/tests/fixtures/projects/
  - atlas-vault-documentation/tests/test_ingestion_stage2.py
  - atlas-vault-documentation/scripts/benchmark_ingestion.py
  - atlas-vault-documentation/AS-WP-004-CERTIFICATION.md
validation: passed
sync_state: synchronized
blockers: []
```

```yaml
schema_version: 1
receipt_type: atlas-control-plane-concurrency-reconciliation
work_package_id: AS-CTRL-001
status: passed
historical_failure_preserved: true
root_cause: shared-state-ordering-race
fix: per-Vault lock covers capture-through-normalize-through-route
focused_test: test_managed_launcher_automates_ack_capability_and_postflight
repetitions: 10
passed: 10
failed: 0
full_control_plane_tests: 146
evidence: evidence/AS-CTRL-001-concurrency-reconciliation.json
sync_state: synchronized
blockers: []
```

```yaml
schema_version: 1
receipt_type: atlas-control-plane-certification
work_package_id: AS-CTRL-001
status: certified
skill_dependency:
  work_package: AS-SKILL-001
  status: certified
  skill_id: atlas-governed-work
  version: 1.0.0
  sha256: 2d8eb525631e27800ffac120b5a79ac712fad58489879d96a3ad535cf8da4123
managed_launcher:
  online_session: passed
  automatic_session_start: passed
  environment_injection: passed
  postflight_enforcement: passed
multi_agent:
  sessions: 2
  completed: 2
  unique_session_ids: true
  unique_event_ids: true
offline:
  synchronized: true
  pending_spool: 0
repository_enforcement:
  missing_receipt_rejected: true
  protected_path_write_rejected: true
validation:
  focused_tests: 12
  subproject_tests: 146
  parent_tests: 54
  mypy: passed
  ruff: passed
  compilation: passed
sync_state: synchronized
blockers: []
```

```yaml
schema_version: 1
receipt_type: atlas-work-package-certification
work_package_id: AS-CTRL-001
status: certified
skill:
  id: atlas-vault-documentation
  version: 1.0.0
  sha256: e830c4fcec547640ecb618c4d80d0256c39b49cf7075f4af57aaf7b38dc40ee9
control:
  bootstrap: implemented
  logical_vault_identity: implemented
  generated_adapters: implemented
  session_identity: implemented
  event_surface: implemented
  receipt_gate: implemented
validation:
  focused_tests: 7
  parent_tests: 54
  mypy: passed
  ruff: passed
  managed_end_to_end_pipeline: pending
  spool_sync: pending
sync_state: certification-pending

---

schema_version: 1
receipt_type: atlas-skill-certification
work_package_id: AS-SKILL-001
status: implementation-complete-certification-pending
skill:
  id: atlas-governed-work
  version: 1.0.0
  sha256: 2d8eb525631e27800ffac120b5a79ac712fad58489879d96a3ad535cf8da4123
validation:
  online_cli_rehearsal: passed
  offline_spool_sync: passed
  negative_gate_evidence: passed
  negative_gate_matrix: passed
  readiness_promotion_generic_cli: passed
  readiness_promotion_development_agent: pending
sync_state: synchronized
blockers:
    - real managed normalize-verify-route session evidence pending
    - offline spool synchronization evidence pending

---

schema_version: 1
receipt_type: atlas-skill-certification
skill_id: atlas-governed-work
work_package_id: AS-SKILL-001
status: certified
skill_version: 1.0.0
skill_sha256: 2d8eb525631e27800ffac120b5a79ac712fad58489879d96a3ad535cf8da4123
validation:
  skill_package: passed
  adapter_generation: passed
  focused_lifecycle_pipeline: passed
  readiness_rehearsal: passed
  negative_gate_matrix: passed
sync_state: synchronized
```

```yaml
schema_version: 1
receipt_type: atlas-work-package-certification
work_package_id: AS-WP-005
status: certified
focused_tests: 5
subproject_tests: 134
parent_tests: 54
graphify:
  inventory_backed: true
  schemas: [graphify-1.0]
  authority: derived
  semantic_ingestion: enabled
  canonical_override_allowed: false
golden:
  nodes: ingested
  source_linked_relationship: verified
  duplicate_collapse: passed
  orphan_quarantine: passed
  inferred_relationship: retained
incremental:
  no_op_replay: passed
  artifacts_reparsed: 0
  state_drift: 0
performance:
  benchmark_status: passed
  small_first_ingestion_median_seconds: 0.02445
  medium_first_ingestion_median_seconds: 0.57966
  large_first_ingestion_median_seconds: 7.92459
  large_no_op_median_seconds: 0.70032
validation:
  mypy: passed
  ruff: passed
  compilation: passed
  strict_graph_validation: passed
sync_state: synchronized
blockers: []
```
