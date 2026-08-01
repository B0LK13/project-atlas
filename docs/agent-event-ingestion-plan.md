# AS-INT-001 Work Plan

## Objective

Connect verified Atlas Control Plane event packages to Atlas Core through a
small typed contract and the public Core discovery/ingestion workflow.

## Deliverables

1. Versioned `atlas_contracts` models and JSON schemas.
2. Deterministic package inspection with root confinement and hash checks.
3. `atlas discover` inventory entries for agent-event packages.
4. `atlas ingest` revalidation, source preservation, state and quarantine.
5. Project activity, session, validation, decision, blocker and work-package
   projections.
6. Controlled valid/pending/malformed/conflicting/traversal fixture coverage.
7. Deterministic replay and strict Vault validation evidence.

## Requirements mapping

| Requirement | Evidence |
|---|---|
| Separate Core/Control Plane ownership | `docs/adr/ADR-003-agent-event-ingestion-contract.md` |
| Typed identity/provenance/receipt contract | `src/atlas_contracts/`, schema lockstep tests |
| Independent ingestion trust boundary | `atlas_contracts.event_package`, ingestion integration tests |
| Event classifications and projections | `test_public_event_package_workflow_and_projections` |
| Quarantine invalid/pending/conflicting packages | `test_pending_malformed_and_traversal_packages_are_explicitly_quarantined`, hash/Vault tests |
| Duplicate and replay behavior | duplicate-ID and repeated-package tests |
| Public CLI workflow | all AS-INT-001 integration tests use `project_atlas.cli.main` |

## Exit gates

- shared contract tests and schemas pass;
- Core and Control Plane suites pass without Control Plane source changes;
- Ruff, mypy and compilation pass;
- valid fixture compiles complete activity history;
- invalid packages produce no canonical event projection and no escaped write;
- unchanged replay has zero content drift, canonical changes and filesystem writes;
- strict Vault validation passes;
- receipt remains `IMPLEMENTATION COMPLETE — CERTIFICATION PENDING` until
  independent review.
