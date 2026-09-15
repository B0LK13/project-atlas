# 5. Phase 0 — Program Foundation

**Status:** Completed

## Objective

Define the Atlas vision, repository structure, documentation philosophy, evidence hierarchy and modular implementation approach.

## Core deliverables

* Project Atlas charter;
* Atlas Vault information architecture;
* `atlas-vault-documentation` subproject;
* implementation roadmap;
* acceptance criteria;
* work-package model;
* documentation receipts;
* source-authority hierarchy;
* raw versus derived artifact rules.

## Exit condition

A stable architecture exists for building the pipeline incrementally without requiring uncontrolled Vault writes.

---

# 6. Phase 1 — Deterministic Capture and Validation

**Work package:** AS-WP-001
**Status:** Certified

## Delivered capabilities

* immutable event capture;
* path-safe and atomic writes;
* configuration discovery;
* CLI, environment, config and default precedence;
* strict spool validation;
* secret redaction;
* JSON command contracts;
* duplicate event rejection;
* symlink and traversal protection;
* deterministic event IDs;
* documentation receipts.

## Strategic value

This phase created Atlas’s evidence boundary. Project and agent activity can now be recorded without mutating raw evidence or writing outside approved roots.

## Certification baseline

* 60 focused tests;
* parent regression suite green;
* Ruff and mypy clean;
* strict documentation validation passed.

---

# 7. Phase 2 — Normalization, Verification and Provenance

**Work package:** AS-WP-002
**Status:** Certified

## Delivered capabilities

* governed `mda-cli` orchestration;
* explicit command arrays without shell construction;
* timeout and bounded retry behavior;
* sibling and output-directory modes;
* normalized artifact verification;
* SHA-256 provenance;
* raw-to-normalized lineage;
* structured failure records;
* secret-redacted process output;
* normalization receipts;
* distinct raw and normalized validation rules.

## Strategic value

Atlas can transform captured evidence into readable normalized documentation while retaining cryptographic traceability to the original source.

## Remaining operational note

The first live provider deployment should continue to confirm actual `mda-cli` output behavior against the certified mock contract.

---

# 8. Phase 3 — Canonical Routing and Safe Projection

**Work package:** AS-WP-003
**Status:** Certified

## Delivered capabilities

* stable project identity;
* canonical project routing;
* project activity logs;
* work-package projections;
* generated-region safety;
* transaction boundaries;
* routing state;
* immutable route receipts;
* duplicate replay handling;
* concurrent agent protection;
* stale-state rejection;
* strict route validation.

## Strategic value

This phase created the only approved write path into canonical Atlas project records.

Agents and ingestion systems now submit verified artifacts rather than editing Atlas project pages directly.

---

# 9. Phase 4 — Project Discovery and Documentation Ingestion

**Work package:** AS-WP-004
**Status:** Certified

## Delivered capabilities

* bounded project discovery;
* optional Atlas project manifests;
* deterministic document inventory;
* streaming SHA-256 hashing;
* document classification;
* source-authority assignment;
* sensitive file protection;
* unsupported format inventory;
* incremental ingestion state;
* new, changed, deleted and renamed document handling;
* documentation-map generation;
* coverage assessment;
* conflict reporting;
* strict transaction rollback;
* Graphify metadata-only discovery;
* project ingestion receipts.

## Controlled fixture coverage

* documentation-rich project;
* sparse README project;
* monorepo;
* mixed-format project;
* Graphify-present project.

## Strategic value

Atlas can now convert a repository’s documentation estate into governed, traceable and navigable project knowledge.

---

[...excerpt boundary...]

# 10. Phase 5 — Universal Agent Governance

This phase contains two related but distinct work packages.

---

## 10.1 AS-SKILL-001 — Governed Work Skill

**Status:** Certified

## Delivered capabilities

* canonical `atlas-governed-work` skill;
* deterministic manifest and skill hashing;
* minimal generated bootstrap shims;
* skill acknowledgement;
* capability checks;
* adapter readiness registry;
* lifecycle rehearsal;
* receipt-bound readiness promotion;
* exact-once offline synchronization;
* fail-closed governance probes;
* skill-to-receipt binding.

## Strategic value

Agents now receive the operational knowledge required to use Atlas correctly.

The skill teaches:

```text
Bootstrap
→ Acknowledge
→ Capability check
→ Document work
→ Validate
→ Obtain receipt
→ Postflight
```

The underlying CLI continues to orchestrate the security-sensitive stages.

---

## 10.2 AS-CTRL-001 — Atlas Control Plane

**Status:** Certified
**Priority:** Immediate

## Objective

Prove that every managed agent is automatically bound to the certified skill, correct project, correct logical Vault and mandatory documentation lifecycle.

## Remaining certification deliverables

### Managed launcher

Certify that `atlas-agent run` automatically performs:

* project resolution;
* Vault verification;
* adapter readiness validation;
* skill resolution;
* acknowledgement enforcement;
* capability checks;
* session allocation;
* environment injection;
* automatic session-start capture;
* child-process execution;
* postflight validation;
* receipt enforcement.

### Shared-Vault multi-agent operation

Prove:

* unique session identities;
* unique event identities;
* safe concurrent routing;
* idempotent identical replay;
* conflicting duplicate rejection;
* independent session receipts.

### Repository enforcement

Implement or certify:

* repository bootstrap shims;
* adapter drift gates;
* protected-path enforcement;
* change-without-receipt rejection;
* stale or wrong-project receipt rejection;
* CI validation.

### Final certification exit criteria

```text
AS-CTRL-001 CERTIFIED
```

Only when:

* managed online session passes;
* managed offline session synchronizes;
* multi-agent shared-Vault operation passes;
* postflight rejects incomplete sessions;
* repository and CI gates pass;
* direct protected-path writes are rejected;
* strict validation is green.

## Program gate

AS-CTRL-001 certification is complete. Broad work remains bounded by the
reconciled architecture: Atlas Core owns the canonical Vault and Control Plane
events must enter Core through a governed source-package contract.

---
