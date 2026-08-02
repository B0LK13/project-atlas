# Project Atlas — Master Roadmap

**Roadmap version:** 1.0
**Roadmap date:** August 1, 2026
**Program status:** Atlas Core vertical slice merged; AS-INT-001 certified; AS-CORE-002 certification reopened for source-lifecycle remediation
**Target state:** Governed, evidence-backed project intelligence system built on an Obsidian-compatible Atlas Vault

---

# 1. Executive Vision

Project Atlas will become the authoritative knowledge and documentation layer for all development projects, agents, work packages, architectural decisions, validation evidence, dependencies, risks and operational status.

Atlas is not intended to be a bulk document archive.

It is a governed project intelligence platform that converts fragmented source material and agent activity into:

* structured project records;
* traceable implementation history;
* normalized and verified documentation;
* evidence-backed project status;
* documentation coverage maps;
* architecture and dependency relationships;
* cross-project intelligence;
* agent session receipts;
* operational health and synchronization reporting.

The target lifecycle is:

```text
Discover
→ Capture
→ Normalize
→ Verify
→ Route
→ Ingest
→ Relate
→ Project
→ Validate
→ Synchronize
→ Audit
```

Every material claim in Atlas should remain traceable to authoritative source evidence.

---

# 2. Strategic Principles

Project Atlas must preserve the following guarantees throughout every phase:

## Evidence before interpretation

Raw project evidence remains immutable. Normalized documents, summaries, relationship graphs and dashboards are derived representations.

## One governed write path

Agents and ingestion systems must not directly modify canonical Atlas state. All writes must pass through the certified capture, normalization, verification and routing pipeline.

## Machine state plus human projections

Machine-readable JSON, JSONL and receipts provide deterministic state. Markdown and Obsidian pages provide human navigation and interpretation.

## Idempotent by default

Repeated unchanged execution must produce no duplicate events, no duplicate routes and no unnecessary document rewrites.

## Fail closed

Invalid identities, conflicting events, malformed evidence, stale receipts, wrong Vaults and corrupted spool records must never enter canonical state silently.

## Progressive adoption

Atlas should first prove correctness on controlled fixtures and bounded project groups before estate-wide synchronization is enabled.

## Graph data remains derived

Graphify and future graph-analysis systems complement authoritative project evidence but never override it automatically.

---

# 3. Current Program Status

## Reconciled architecture

Project Atlas is organized as three complementary streams. **Atlas Core** is
`src/project_atlas/` and owns the canonical OKF Vault compiler. **Atlas Control
Plane** is `atlas-vault-documentation/` and produces governed agent-event
evidence, receipts, and synchronization state. The future **Atlas Graph Layer**
contains derived, source-linked relationship intelligence. The accepted
decision is recorded in `docs/adr/ADR-002-atlas-two-track-reconciliation.md`.

Atlas Core's controlled `discover → ingest → build-indexes → validate` vertical
slice is merged and tagged. AS-INT-001 and AS-CORE-002 are certified. Atlas
Core is not yet an MVP.

## Certified foundations

| Work package | Capability                                               | Status        |
| ------------ | -------------------------------------------------------- | ------------- |
| AS-WP-001    | Deterministic capture and validation                     | **Certified** |
| AS-WP-002    | Normalization, verification and provenance               | **Certified** |
| AS-WP-003    | Atlas router and canonical projections                   | **Certified** |
| AS-WP-004    | Project discovery, inventory and documentation ingestion | **Certified** |
| AS-SKILL-001 | `atlas-governed-work` operational agent skill            | **Certified** |

## Certified control plane

| Work package | Capability                                                    | Status                                              |
| ------------ | ------------------------------------------------------------- | --------------------------------------------------- |
| AS-CTRL-001  | Universal agent bootstrap and Atlas documentation enforcement | **Certified** |

## Integration stream

| Work package | Capability | Status |
|---|---|---|
| AS-INT-001 | Governed Control Plane event-package ingestion into Atlas Core | **Certified** |
| AS-CORE-002 | Semantic domain model and source lifecycle hardening | **Certification reopened — remediation in progress** |

## Authorized next work

| Work package | Capability                                    | Status                                 |
| ------------ | --------------------------------------------- | -------------------------------------- |
| AS-CORE-002 | Semantic domain model and source lifecycle hardening | **Certified; deferred follow-up remains** |
| AS-WP-005    | Graphify adapter and relationship projections | **Deferred until Core integration boundary is established** |

---

# 4. Program Roadmap Overview

```text
PHASE 0  Program foundation and architecture
   ↓
PHASE 1  Capture, validation and immutable evidence
   ↓
PHASE 2  Normalization, provenance and verification
   ↓
PHASE 3  Canonical routing and safe Atlas projections
   ↓
PHASE 4  Project discovery and documentation ingestion
   ↓
PHASE 5  Agent skill and control-plane enforcement
   ↓
PHASE 6  Graphify relationship intelligence
   ↓
PHASE 7  Cross-project knowledge model
   ↓
PHASE 8  Bounded real-project synchronization pilot
   ↓
PHASE 9  Estate-wide incremental synchronization
   ↓
PHASE 10 Search, analytics and operational dashboard
   ↓
PHASE 11 Production hardening and long-term governance
```

---

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

# 11. Phase 6 — Graphify Relationship Intelligence

**Work package:** AS-WP-005
**Status:** Next capability after control-plane certification

## Objective

Convert Graphify output files into validated, provenance-backed Atlas relationship records.

## Core deliverables

### Graphify adapters

Support controlled formats such as:

* `graph.json`;
* `nodes.json`;
* `edges.json`;
* JSONL node and edge streams;
* Graphify metadata files.

### Canonical node model

Initial entity types:

* project;
* component;
* service;
* module;
* document;
* decision;
* requirement;
* work package;
* validation;
* agent;
* skill;
* technology;
* deployment target;
* data store;
* external system.

### Canonical relationship model

Initial relationships:

* `part-of`;
* `depends-on`;
* `implements`;
* `documents`;
* `validates`;
* `tests`;
* `blocks`;
* `supersedes`;
* `generated-by`;
* `deployed-to`;
* `stores-data-in`;
* `invokes`;
* `derived-from`;
* `conflicts-with`.

### Entity resolution

Deterministic precedence:

```text
Explicit Atlas identity
→ Explicit document identity
→ Configured mapping
→ Stable project-local identity
→ Exact alias
→ Unresolved
```

No fuzzy or LLM-based identity resolution in this phase.

### Source-document linkage

Every verified relationship should link to one or more AS-WP-004 document records.

### Verification states

* verified;
* supported;
* inferred;
* unverified;
* conflicting;
* orphaned.

### Quarantine

Invalid, ambiguous or orphaned graph records must enter governed quarantine rather than canonical graph state.

### Human-readable projections

Generate:

* `relationships.md`;
* `dependencies.md`;
* `architecture-map.md`;
* `document-lineage.md`;
* `decision-lineage.md`;
* `work-package-map.md`;
* `graph-health.md`.

### Machine-readable stores

```text
relationships/
├── nodes/<project-id>.jsonl
├── edges/<project-id>.jsonl
├── state/<project-id>.json
├── receipts/
├── failures/
└── quarantine/
```

## Exit criteria

* deterministic Graphify schema acceptance;
* node and edge normalization;
* source-linked verification;
* duplicate collapse;
* conflict detection;
* orphan quarantine;
* incremental graph replay;
* strict graph validation;
* no canonical override by derived Graphify data.

---

# 12. Phase 7 — Cross-Project Knowledge Model

**Proposed work package:** AS-WP-006
**Status:** Planned

## Objective

Extend Atlas from isolated project graphs into a governed cross-project knowledge model.

## Core deliverables

### Global entity identities

Create governed identities for shared entities:

* technologies;
* services;
* infrastructure;
* agents;
* skills;
* deployment environments;
* shared libraries;
* external APIs;
* organizations or teams.

### Cross-project relationship rules

Support:

* project depends on shared service;
* project deploys to common platform;
* project uses shared library;
* project supersedes another project;
* project shares architecture component;
* project is blocked by common dependency.

### Duplicate project detection

Identify:

* duplicate clones;
* renamed projects;
* archived forks;
* successor repositories;
* monorepo overlaps.

### Conflict intelligence

Surface:

* inconsistent dependency versions;
* contradictory architecture claims;
* stale shared configuration;
* duplicate work-package identifiers;
* divergent deployment documentation;
* obsolete shared components.

### Global Atlas indexes

Generate:

```text
Atlas/
├── Projects/
├── Technologies/
├── Components/
├── Services/
├── Agents/
├── Skills/
├── Work-Packages/
├── Decisions/
├── Risks/
└── Relationships/
```

## Exit criteria

* cross-project edges require explicit identities;
* no name-only merging;
* evidence remains project-scoped;
* conflicting relationships remain visible;
* access and privacy boundaries are documented.

---

# 13. Phase 8 — Bounded Real-Project Synchronization Pilot

**Proposed work package:** AS-WP-007
**Status:** Planned

## Objective

Validate Atlas against a controlled set of real development projects before estate-wide deployment.

## Recommended pilot portfolio

1. Project Atlas;
2. one mature Python project;
3. one modern TypeScript or Next.js project;
4. one monorepo;
5. one documentation-sparse or archived project;
6. one project with Graphify outputs.

Potential candidates from the existing environment may include:

* Obsidian Agent;
* Dark Factory;
* AI Budget Coach;
* autonomous-loop;
* Black Agency OS / LLM-Wiki.

The final selection should be explicit and bounded.

## Pilot workflow

### Dry run

Review:

* project identities;
* discovered documents;
* sensitive exclusions;
* unsupported formats;
* estimated normalization volume;
* planned routes;
* Graphify artifacts;
* projected Atlas structure.

### Controlled ingestion

Ingest projects one at a time.

### Human review

Evaluate:

* navigation usefulness;
* classification accuracy;
* coverage usefulness;
* conflict noise;
* graph quality;
* status accuracy;
* source traceability.

### Incremental replay

Run repeated synchronization and confirm:

* no-op behavior;
* targeted changed-document processing;
* deleted-source retention;
* graph update correctness;
* receipt integrity.

## Pilot success metrics

* ≥95% correct high-confidence classifications;
* 100% source traceability for generated claims;
* 0 uncontrolled secret ingestion;
* 0 writes outside configured roots;
* 0 duplicate routed events;
* ≥90% useful relationship precision in reviewed graph projections;
* no-op replay produces zero canonical mutations;
* strict validation remains green.

---

# 14. Phase 9 — Estate-Wide Incremental Synchronization

**Proposed work package:** AS-WP-008
**Status:** Planned

## Objective

Scale Atlas from a controlled pilot to the full configured development estate.

## Core capabilities

### Workspace registry

Maintain explicit workspace roots and project policies.

### Scheduled synchronization

Support:

* manual runs;
* startup scans;
* scheduled scans;
* repository-triggered scans;
* post-agent-session scans.

### Change detection

Use:

* content fingerprints;
* repository state;
* document revisions;
* Graphify artifact hashes;
* receipt history.

### Queue and retry model

Handle:

* temporary provider failures;
* locked files;
* offline Vault;
* quarantined records;
* stale transactions;
* partial project availability.

### Resource controls

Add:

* bounded concurrency;
* file-size limits;
* project priorities;
* scan budgets;
* provider rate limits;
* backpressure;
* cancellation.

### Operational receipts

Produce estate-level synchronization receipts summarizing:

* projects scanned;
* projects changed;
* documents processed;
* relationships updated;
* failures;
* quarantine;
* pending spool;
* validation state.

## Exit criteria

* estate-wide no-op run remains efficient;
* one failed project cannot corrupt others;
* synchronization is resumable;
* every project retains transaction isolation;
* control-plane and receipt enforcement remain active.

---

# 15. Phase 10 — Search, Analytics and Project Dashboard

**Proposed work package:** AS-WP-009
**Status:** Planned

## Objective

Expose Atlas intelligence through useful human and agent interfaces.

## Core deliverables

### Obsidian navigation

* project dashboards;
* project MOCs;
* recent activity;
* work-package indexes;
* decision indexes;
* risk indexes;
* technology indexes;
* dependency maps.

### Search

Support:

* full-text search;
* metadata search;
* relationship search;
* event search;
* source-backed question answering;
* project comparison.

### Portfolio dashboard

Display:

* project status;
* completion;
* active work packages;
* recent validations;
* blockers;
* documentation coverage;
* stale documents;
* unresolved conflicts;
* dependency health;
* agent activity;
* synchronization state.

### Analytics

Track:

* documentation freshness;
* project activity cadence;
* validation frequency;
* failure and retry rates;
* work-package lead time;
* unresolved risk age;
* graph source-link coverage;
* agent receipt compliance.

### Agent query interface

Allow agents to ask:

* What is the current project status?
* Which work package is active?
* What changed recently?
* Which documents are authoritative?
* Which validations support completion?
* Which dependencies are unresolved?
* What must be documented next?

## Exit criteria

Dashboards and search must derive from canonical Atlas records and must never become separate sources of truth.

---

# 16. Phase 11 — Production Hardening and Governance

**Proposed work package:** AS-WP-010
**Status:** Planned

## Objective

Make Atlas reliable for long-term daily operation.

## Core deliverables

### Backup and recovery

* version-controlled Vault where appropriate;
* immutable evidence backup;
* off-site backup;
* receipt backup;
* recovery rehearsals;
* corruption detection;
* point-in-time restore guidance.

### Schema evolution

* versioned schemas;
* migration tools;
* backwards compatibility;
* receipt migration policy;
* deprecated schema detection.

### Access control

* protected canonical paths;
* agent write restrictions;
* user roles;
* project boundaries;
* sensitive document policies;
* audit logs.

### Operational observability

* synchronization health;
* pending spool;
* transaction failures;
* normalization failures;
* quarantine growth;
* stale adapter readiness;
* skill drift;
* CI compliance.

### Governance policy

Define:

* source authority;
* retention;
* deletion;
* conflict review;
* graph verification;
* agent certification;
* project retirement;
* archive policy.

### Disaster scenarios

Rehearse:

* wrong Vault mount;
* corrupted routing state;
* interrupted synchronization;
* unavailable provider;
* stale skill;
* compromised adapter;
* partial project deletion;
* duplicate repository clones.

## Exit criteria

Atlas can be restored, audited, upgraded and operated without relying on undocumented tribal knowledge.

---

# 17. Recommended Release Milestones

## Atlas Alpha — Evidence Pipeline

Includes:

* AS-WP-001;
* AS-WP-002;
* AS-WP-003.

**Status:** Achieved

Outcome:

> Agents and tools can capture, normalize, verify and route evidence safely.

---

## Atlas Beta — Project Documentation Intelligence

Includes:

* AS-WP-004;
* AS-SKILL-001;
* AS-CTRL-001.

**Status:** In progress

Outcome:

> Project documentation is governed, and managed agents are automatically required to document their work.

Release gate:

* AS-CTRL-001 certified.

---

## Atlas Graph Beta

Includes:

* AS-WP-005;
* initial Graphify projections;
* graph health reporting.

Outcome:

> Atlas exposes evidence-backed project architecture, dependency and lineage relationships.

---

## Atlas Portfolio Preview

Includes:

* AS-WP-006;
* AS-WP-007;
* bounded multi-project pilot.

Outcome:

> Atlas provides cross-project intelligence for a reviewed portfolio of real projects.

---

## Atlas 1.0

Includes:

* AS-WP-008;
* AS-WP-009;
* AS-WP-010.

Outcome:

> Atlas operates as the production project intelligence and documentation control plane for the full development estate.

---

# 18. Priority Execution Order

## Immediate

1. Establish the Git reconciliation baseline.
2. Implement the Atlas Core `discover → ingest → build-indexes → validate` slice.
3. Define the shared governed agent-event source-package contract.
4. Integrate Control Plane evidence into Atlas Core ingestion.

## Next

5. Implement and certify AS-WP-005 after the Core integration boundary is stable.
6. Validate Graphify source-link quality.
7. Produce project-local relationship projections.
8. Establish graph quarantine and health reporting.

## Then

9. Implement cross-project entity identities.
10. Execute the bounded real-project pilot.
11. Review classifications, coverage and relationships manually.
12. Correct high-noise rules before scaling.

## Later

13. Enable estate-wide incremental synchronization.
14. Build search and portfolio analytics.
15. Add operational monitoring, backup and migration controls.
16. Release Atlas 1.0.

---

# 19. Program-Level Success Metrics

## Evidence integrity

* 100% of routed artifacts retain source provenance;
* 100% of completion events reference validation evidence;
* zero raw evidence mutation;
* zero uncontrolled canonical writes.

## Agent compliance

* 100% of managed implementation sessions use a certified skill;
* 100% of completed sessions have validated receipts;
* zero active adapters with stale readiness;
* zero completion authorization with pending strict spool.

## Ingestion quality

* 100% of discovered files receive an explicit state;
* zero silent unsupported-file drops;
* zero secret-content leakage;
* no-op replay produces zero canonical mutations.

## Documentation intelligence

* every project has a documentation map;
* every project has categorical coverage reporting;
* conflicts remain evidence-backed;
* missing documentation is visible rather than invented.

## Graph quality

* every canonical relationship has provenance;
* inferred relationships are visibly labeled;
* unresolved identities remain quarantined;
* Graphify never overrides primary evidence automatically.

## Operational health

* strict validation remains green;
* transaction failures preserve previous valid state;
* synchronization is resumable;
* backup restoration is periodically rehearsed.

---

# 20. Principal Risks and Mitigations

| Risk                    | Mitigation                                                      |
| ----------------------- | --------------------------------------------------------------- |
| Agents bypass Atlas     | Managed launcher, protected paths, CI receipt gates             |
| Skill drift             | Hash verification, adapter regeneration, readiness invalidation |
| Wrong Vault writes      | Logical Vault ID and UUID verification                          |
| Documentation overload  | Capture meaningful milestones, not every command                |
| Graph noise             | Deterministic resolution, source-link requirements, quarantine  |
| Secret ingestion        | Sensitive-file metadata-only policy and redaction               |
| Duplicate projects      | Repository identity and explicit project manifests              |
| Stale Atlas projections | Incremental state and source revision tracking                  |
| Provider failure        | Immutable raw evidence, retries, spool and failure records      |
| Partial synchronization | Per-project transactions and atomic promotion                   |
| Vault growth            | Retention policy, deduplication and derived-artifact controls   |
| False project status    | Authority hierarchy and evidence-backed projections             |

---

# 21. Definition of Atlas 1.0 Done

Project Atlas reaches version 1.0 when:

* all managed agents automatically load the certified skill;
* AS-CTRL-001 is certified;
* all configured projects can be safely discovered and ingested;
* project documentation maps and coverage reports are generated;
* Graphify relationships are validated and source-linked;
* cross-project identities are governed;
* synchronization is incremental and resumable;
* dashboards derive only from canonical Atlas state;
* strict validation passes estate-wide;
* backups and restoration are proven;
* every material project claim can be traced to evidence;
* no agent can claim governed completion without a valid receipt.

---

# 22. Final Target State

The completed Atlas platform should answer, reliably and with evidence:

* What projects exist?
* What is each project intended to do?
* What is its current lifecycle state?
* What work has been completed?
* Which validation supports that conclusion?
* What work remains?
* Which documentation is missing or stale?
* Which claims conflict?
* Which components and systems are related?
* Which dependencies create risk?
* Which agents performed the work?
* Which skill governed their sessions?
* Has every session been synchronized?
* What changed since the previous scan?
* Can the project’s history be reconstructed from receipts and source evidence?

Project Atlas succeeds when it becomes the trusted reconstruction layer for the entire project estate—not merely another place where documents are stored.

## AS-ID-001 — Durable Source Lineage Identity

Implementation is complete pending governor review. The certified baseline is
kept unchanged while the candidate adds UUIDv4 project genesis, registry v2,
source-lineage continuity, raw-byte fingerprints, atomic migration receipts,
and fail-closed ambiguity handling. AS-CORE-003 remains a separate frozen
package until this identity contract is reviewed and merged.
