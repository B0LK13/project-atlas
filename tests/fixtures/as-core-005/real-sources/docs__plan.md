# Project concept: **Project Atlas — OKF Project Intelligence Vault**

This is an excellent fit for Google’s **Open Knowledge Format (OKF)**. OKF is intentionally built around plain Markdown, YAML frontmatter, directory-based bundles, source provenance, lifecycle metadata, and cross-linked concepts—exactly the primitives needed for a durable Obsidian project vault. The current specification is **OKF v0.2**, which adds provenance, verification, freshness, lifecycle, and trust signals. ([GitHub][1])

The vault should not become another archive of copied documents. It should become a **portfolio-wide knowledge control plane** that converts scattered project documentation into:

* a standardized project catalog;
* a navigable documentation graph;
* an authoritative status overview;
* a decision and evidence register;
* an AI-agent-readable context repository;
* a foundation for project supervision and portfolio governance.

---

## 1. North-star outcome

At the vault root, you should be able to answer:

> What projects exist, what are they trying to achieve, what is their current state, which documentation is authoritative, what decisions were made, what is blocked, and what should happen next?

For every project, the vault should answer:

1. **What is this project?**
2. **Why does it exist?**
3. **What is the architecture?**
4. **What has already been implemented?**
5. **What is currently operational?**
6. **What evidence supports those claims?**
7. **Which decisions shaped the project?**
8. **What risks and gaps remain?**
9. **Which documents are canonical?**
10. **What is the next logical work package?**

This would turn your existing project landscape—Nebula Control Platform, Black Agency OS, Dark Factory, AI Budget Coach, Obsidian Agent, Autonomous Loop, the media organization system, and future projects—into one coherent operating model.

---

# 2. Core architectural decision

I recommend a **three-layer vault**.

## Layer A — Source evidence

Original project documentation, imported with minimal modification.

Examples:

* README files;
* architecture documents;
* PRPs;
* roadmaps;
* ADRs;
* validation reports;
* test evidence;
* deployment notes;
* agent instructions;
* release reports;
* security reviews;
* repository metadata.

These files remain the factual evidence base.

## Layer B — Canonical knowledge

Small, structured OKF concept documents generated from the sources.

Examples:

* one project concept;
* one component concept;
* one architecture concept;
* one milestone concept;
* one decision concept;
* one risk concept;
* one deployment concept;
* one validation concept.

This is the layer humans and AI agents primarily consume.

## Layer C — Portfolio intelligence

Cross-project views synthesized from the canonical layer.

Examples:

* active projects;
* maturity matrix;
* current blockers;
* deployment status;
* technology inventory;
* shared infrastructure;
* reusable components;
* duplicated capabilities;
* technical debt;
* projects awaiting validation;
* recent project changes.

This separation is critical. It prevents generated summaries from being confused with original evidence.

---

# 3. Recommended vault structure

OKF reserves `index.md` for progressive directory navigation and `log.md` for chronological updates. The format otherwise allows producers to organize concepts according to their domain. ([GitHub][1])

```text
Project-Atlas/
│
├── index.md
├── log.md
├── README.md
│
├── 00-system/
│   ├── index.md
│   ├── vault-charter.md
│   ├── taxonomy.md
│   ├── metadata-schema.md
│   ├── ingestion-policy.md
│   ├── trust-policy.md
│   ├── lifecycle-policy.md
│   ├── linking-policy.md
│   └── naming-conventions.md
│
├── 01-portfolio/
│   ├── index.md
│   ├── portfolio-overview.md
│   ├── active-projects.md
│   ├── maturity-matrix.md
│   ├── strategic-roadmap.md
│   ├── project-dependencies.md
│   ├── shared-platforms.md
│   ├── shared-technology.md
│   ├── portfolio-risks.md
│   └── current-priorities.md
│
├── projects/
│   ├── index.md
│   │
│   ├── nebula-control-platform/
│   │   ├── index.md
│   │   ├── log.md
│   │   ├── project.md
│   │   ├── status.md
│   │   ├── vision.md
│   │   ├── architecture.md
│   │   ├── roadmap.md
│   │   ├── components/
│   │   ├── decisions/
│   │   ├── deployments/
│   │   ├── validations/
│   │   ├── risks/
│   │   ├── runbooks/
│   │   ├── work-packages/
│   │   └── references/
│   │
│   ├── black-agency-os/
│   ├── dark-factory/
│   ├── ai-budget-coach/
│   ├── obsidian-agent/
│   ├── autonomous-loop/
│   └── media-intelligence-organizer/
│
├── capabilities/
│   ├── index.md
│   ├── agent-orchestration/
│   ├── document-intelligence/
│   ├── retrieval/
│   ├── observability/
│   ├── deployment/
│   ├── security/
│   ├── automation/
│   └── user-interfaces/
│
├── infrastructure/
│   ├── index.md
│   ├── hosts/
│   ├── networks/
│   ├── services/
│   ├── environments/
│   ├── storage/
│   └── deployment-targets/
│
├── technologies/
│   ├── index.md
│   ├── frameworks/
│   ├── databases/
│   ├── ai-models/
│   ├── infrastructure-tools/
│   └── development-tools/
│
├── decisions/
│   ├── index.md
│   └── cross-project/
│
├── standards/
│   ├── index.md
│   ├── documentation-standard.md
│   ├── testing-standard.md
│   ├── security-standard.md
│   ├── evidence-standard.md
│   └── project-readiness-standard.md
│
├── sources/
│   ├── index.md
│   ├── repositories/
│   ├── imported-documents/
│   ├── reports/
│   └── manifests/
│
├── generated/
│   ├── dashboards/
│   ├── reports/
│   ├── maps/
│   └── quality-controls/
│
└── templates/
    ├── project.md
    ├── component.md
    ├── decision.md
    ├── milestone.md
    ├── risk.md
    ├── validation.md
    ├── deployment.md
    ├── runbook.md
    └── source-document.md
```

---

# 4. The project concept document

Each project receives one authoritative `project.md`.

```yaml
---
type: Project
title: Nebula Control Platform
description: Distributed platform for AI automation, workspace execution, observability, and infrastructure control.
resource: https://github.com/example/nebula-control-platform

project_id: PRJ-NEBULA
aliases:
  - Nebula
  - Dark Fleet

tags:
  - project
  - ai-infrastructure
  - automation
  - platform

portfolio:
  domain: AI Infrastructure
  strategic_role: Core Platform
  priority: high

lifecycle:
  status: active
  phase: operational-hardening
  started: 2026-01-01

generated:
  by: agent:atlas-ingestion
  at: 2026-08-01T10:00:00Z

verified:
  by: human:B0LK13
  at: 2026-08-01T12:00:00Z

stale_after: 2026-08-15

sources:
  - id: repository-readme
    resource: /sources/repositories/nebula/README.md
    title: Nebula repository README
    author: project:nebula
    last_modified: 2026-07-31

  - id: deployment-report
    resource: /projects/nebula-control-platform/validations/deployment-report.md
    title: VPS deployment validation
    last_modified: 2026-06-17

relationships:
  depends_on:
    - /infrastructure/hosts/vps-01.md
    - /infrastructure/hosts/vps-02.md
    - /infrastructure/hosts/vps-03.md
  provides:
    - /capabilities/agent-orchestration/index.md
    - /capabilities/observability/index.md
  related_projects:
    - /projects/black-agency-os/project.md
---
```

The body would then contain the human-readable project intelligence:

```markdown
# Nebula Control Platform

## Executive summary

## Strategic purpose

## Current operating state

## Core capabilities

## Architecture

## Major components

## Deployment topology

## Completed milestones

## Current workstreams

## Known risks

## Documentation coverage

## Evidence and validation

## Recommended next actions

## Related concepts
```

OKF requires only `type`, while fields such as `title`, `description`, `resource`, and `tags` are standardized but optional. Custom metadata is permitted, making it suitable for portfolio-specific fields such as priority, maturity, owner, phase, and documentation health. ([GitHub][1])

---

# 5. Recommended knowledge types

Avoid turning every imported document into the generic type `Document`. That would destroy the semantic value of the vault.

Use a controlled but extensible concept taxonomy.

| Type                | Purpose                                                |
| ------------------- | ------------------------------------------------------ |
| `Project`           | Primary project identity and executive overview        |
| `Project Status`    | Current operational and delivery state                 |
| `Component`         | Service, package, module, application, or subsystem    |
| `Architecture`      | Structural or deployment design                        |
| `Capability`        | Reusable ability delivered by one or more projects     |
| `Decision`          | Architectural or strategic decision                    |
| `Requirement`       | Functional or non-functional requirement               |
| `Work Package`      | Bounded delivery unit                                  |
| `Milestone`         | Significant delivery checkpoint                        |
| `Validation`        | Test, certification, benchmark, or evidence result     |
| `Deployment`        | Environment or release deployment                      |
| `Environment`       | Development, test, staging, production, edge, or local |
| `Risk`              | Known uncertainty or exposure                          |
| `Issue`             | Concrete defect or blocker                             |
| `Runbook`           | Repeatable operational procedure                       |
| `Standard`          | Organization-wide policy or engineering standard       |
| `Reference`         | Imported or external supporting source                 |
| `Repository`        | Source-code repository identity                        |
| `Agent Instruction` | Operating directive for an AI agent                    |
| `Dataset`           | Dataset or knowledge corpus                            |
| `Metric`            | Defined measurable indicator                           |
| `Release`           | Versioned software delivery                            |
| `Finding`           | Audit, security, quality, or review finding            |

OKF deliberately avoids enforcing a global type registry, so these project-specific types remain valid while unknown types should still be treated as generic concepts by consumers. ([GitHub][1])

---

# 6. Source-of-truth model

The vault needs an explicit authority hierarchy.

## Proposed authority levels

| Level                             | Meaning                                         |
| --------------------------------- | ----------------------------------------------- |
| **A — Verified canonical**        | Human-confirmed project truth                   |
| **B — Evidence-backed generated** | Generated from identified authoritative sources |
| **C — Imported source**           | Original documentation, not normalized          |
| **D — Inferred**                  | Reasonable synthesis requiring verification     |
| **E — Historical or superseded**  | Retained for traceability, not current truth    |

Do not store a subjective numeric “trust score.” OKF v0.2 instead recommends storing objective signals—source, author, verification, timestamps, freshness, and lifecycle—from which a consumer can determine trust. ([GitHub][1])

A useful custom field could therefore be:

```yaml
knowledge_state: evidence-backed
review_state: pending-human-review
```

Rather than:

```yaml
trust_score: 87
```

---

# 7. Status and lifecycle vocabulary

Every important concept should have a lifecycle state.

```yaml
status: active
```

Recommended vocabulary:

```text
proposed
planned
active
blocked
validation
operational
maintenance
paused
deprecated
superseded
archived
unknown
```

For documents:

```text
draft
review-required
verified
canonical
superseded
historical
```

For implementation maturity:

```text
concept
prototype
mvp
beta
production-candidate
production
hardened
```

Keep these dimensions separate. A project can be:

```yaml
status: active
maturity: mvp
review_state: verified
```

That is much more expressive than a single ambiguous status field.

---

# 8. Evidence-first ingestion pipeline

The most important principle should be:

> **No claim without a traceable source.**

## Stage 1 — Discovery

Scan all approved project-documentation locations:

* Git repositories;
* documentation directories;
* Google Drive project folders;
* exported chats and agent reports;
* local development folders;
* Markdown vaults;
* PDFs and Word documents;
* test and certification evidence;
* deployment manifests.

Produce a source manifest:

```yaml
---
type: Source Manifest
title: Dark Factory documentation inventory
project: PRJ-DARK-FACTORY
generated:
  by: agent:atlas-discovery
  at: 2026-08-01T10:00:00Z
---

documents_found: 184
documents_selected: 91
documents_excluded: 93
duplicates_detected: 17
canonical_candidates: 24
```

## Stage 2 — Classification

Classify each document by:

* project;
* document type;
* authority;
* lifecycle;
* subject;
* date;
* repository;
* work package;
* related components;
* likely canonical status.

## Stage 3 — Extraction

Extract atomic knowledge:

* project objectives;
* architecture;
* components;
* dependencies;
* decisions;
* milestones;
* tests;
* known failures;
* deployments;
* risks;
* next actions.

## Stage 4 — Normalization

Convert extracted information into OKF concept files.

One note should represent one meaningful concept rather than one arbitrary source file.

## Stage 5 — Linking

Create explicit links between:

```text
Project → Component
Project → Repository
Component → Deployment
Decision → Component
Validation → Release
Risk → Project
Runbook → Service
Work Package → Milestone
Project → Capability
```

Normal Markdown links are sufficient to form this graph; OKF consumers can derive relationships and backlinks from those links. ([GitHub][2])

## Stage 6 — Contradiction detection

When two sources disagree:

```yaml
consistency:
  state: conflicting
  conflicts:
    - source: architecture-v1
      claim: Uses Redis 7
    - source: deployment-report
      claim: Uses Redis 8
```

The system should not silently pick one.

## Stage 7 — Human verification

Only promote content to `canonical` after review.

## Stage 8 — Continuous refresh

On every repository or documentation update:

1. identify changed sources;
2. determine affected concepts;
3. regenerate only those concepts;
4. update backlinks and indexes;
5. preserve manual sections;
6. create a change entry in `log.md`;
7. mark uncertain content for review.

---

# 9. Protecting human edits

A major risk is agents overwriting carefully curated notes.

Use section ownership:

```markdown
<!-- BEGIN GENERATED: executive-summary -->
Generated project summary.
<!-- END GENERATED: executive-summary -->

<!-- BEGIN HUMAN: strategic-observations -->
Human-maintained interpretation.
<!-- END HUMAN: strategic-observations -->
```

The generator may update only generated regions.

An even safer model is:

```text
project.generated.md
project.review.md
project.md
```

Where:

* `project.generated.md` is machine-owned;
* `project.review.md` contains proposed changes;
* `project.md` is canonical and human-approved.

For your workflow, I would use the **single-file protected-region model** for ordinary notes and the **three-file model** for highly strategic project summaries.

---

# 10. The portfolio dashboard

The main `01-portfolio/portfolio-overview.md` should provide an executive control surface.

## Suggested sections

### Portfolio snapshot

| Project                 | Phase                  |             Maturity | Health | Documentation | Last verified |
| ----------------------- | ---------------------- | -------------------: | -----: | ------------: | ------------: |
| Nebula Control Platform | Hardening              |           Production |  Green |           82% |    2026-08-01 |
| Black Agency OS         | Retrieval expansion    | Production candidate |  Green |           76% |    2026-07-30 |
| Dark Factory            | Deployment preparation |                  MVP |  Amber |           64% |    2026-07-29 |
| AI Budget Coach         | Staging validation     |                  MVP |  Amber |           71% |    2026-07-28 |
| Obsidian Agent          | Performance validation |                 Beta |  Green |           88% |    2026-07-27 |

### Cross-project blockers

### Projects requiring decisions

### Documentation freshness warnings

### Unverified claims

### Recently completed milestones

### Shared capabilities

### Duplicate or overlapping initiatives

### Highest-leverage next actions

---

# 11. Project documentation completeness model

Each project should be evaluated against a standard documentation blueprint.

```yaml
documentation_coverage:
  project_overview: complete
  architecture: complete
  roadmap: partial
  requirements: complete
  decisions: partial
  deployment: complete
  operations: partial
  testing: complete
  security: missing
  recovery: missing
  agent_instructions: complete
```

Then calculate a transparent completeness indicator.

Do not use a vague score only. Show the missing items:

```markdown
## Documentation gaps

- Missing threat model
- No recovery procedure
- Two unverified deployment assumptions
- Architecture document has not been reviewed since June 2026
```

This makes the vault operational rather than decorative.

---

# 12. A project dependency graph

The portfolio should express dependencies at multiple levels.

## Infrastructure dependency

```text
Black Agency OS
    → Qdrant
    → PostgreSQL
    → VPS-01
```

## Capability dependency

```text
Distill
    → Document ingestion
    → Structured summarization
    → Citation anchoring
```

## Governance dependency

```text
Production release
    → Security review
    → Validation evidence
    → Deployment approval
```

## Knowledge dependency

```text
Project overview
    → Architecture
    → Repository README
    → Deployment validation
```

This allows an agent to answer:

> What would be affected if Qdrant became unavailable?

Or:

> Which projects depend on the same summarization capability?

---

# 13. Capability-centric views

Projects should not be the only organizing dimension.

A capability layer might reveal:

```text
Agent orchestration
├── Autonomous Loop
├── Nebula Control Platform
├── Obsidian Agent
└── Black Agency OS

Retrieval and knowledge
├── Black Agency OS
├── Obsidian Agent
├── Distill
└── Project Atlas

Observability
├── Nebula Control Platform
├── Dark Factory
└── AI Budget Coach
```

This is valuable because your portfolio contains reusable technical assets that may otherwise be repeatedly rebuilt inside separate projects.

It can expose:

* duplication;
* consolidation opportunities;
* reusable libraries;
* platform candidates;
* shared security controls;
* shared deployment components;
* projects that should merge;
* projects that should remain separate.

---

# 14. Automated indexes

Every directory should contain an automatically maintained `index.md`.

Example:

```markdown
---
type: Index
title: Nebula Control Platform
description: Progressive project index for the Nebula Control Platform.
generated:
  by: agent:atlas-indexer
  at: 2026-08-01T10:00:00Z
---

# Nebula Control Platform

## Project

- [Project overview](./project.md)
- [Current status](./status.md)
- [Architecture](./architecture.md)
- [Roadmap](./roadmap.md)

## Components

- [n8n automation service](./components/n8n.md)
- [Qdrant vector database](./components/qdrant.md)
- [Flowise](./components/flowise.md)
- [LangGraph runtime](./components/langgraph.md)

## Current work packages

- [Observability hardening](./work-packages/observability-hardening.md)
- [Backup verification](./work-packages/backup-verification.md)

## Open risks

- [VPS dependency concentration](./risks/vps-concentration.md)

## Recent validations

- [Platform deployment validation](./validations/platform-validation.md)
```

Progressive `index.md` files are an explicit OKF pattern for navigating large bundles without loading the entire corpus into context. ([GitHub][2])

---

# 15. Agent-facing context packs

The vault can generate purpose-specific context bundles.

## Examples

### Development context

```text
Project overview
Architecture
Active work package
Relevant decisions
Coding standards
Current risks
Latest validation
```

### Security review context

```text
Threat model
Architecture
Trust boundaries
Dependencies
Deployment topology
Security decisions
Open findings
```

### Deployment context

```text
Release
Environment
Deployment procedure
Secrets requirements
Rollback plan
Validation checklist
```

### Executive context

```text
Strategic objective
Current maturity
Recent progress
Blockers
Risks
Next decisions
```

This avoids dumping the entire vault into an AI context window.

---

# 16. Quality gates

Every generated concept should pass automated validation.

## Structural gates

* valid YAML;
* required `type`;
* valid path links;
* no duplicate concept identifier;
* reserved filenames used correctly;
* timestamps in a consistent format.

## Provenance gates

* generated claims contain at least one source;
* source files exist;
* source paths are resolvable;
* generated timestamp exists;
* verification state is explicit.

## Content gates

* no unsupported status claims;
* no hidden contradictions;
* no orphan notes;
* no empty project overview;
* no active project without a status note;
* no production project without deployment evidence;
* no completed milestone without validation or supporting source.

## Freshness gates

* active status note not older than 14 days;
* deployment documentation not older than the deployed release;
* architecture marked stale after major component changes;
* project overview refreshed after roadmap changes.

---

# 17. MVP scope

The first version should not ingest every project immediately.

## Recommended pilot projects

Start with three distinct project profiles:

1. **Nebula Control Platform**
   Tests infrastructure, deployment, services, runbooks, and operational documentation.

2. **Black Agency OS / LLM-Wiki**
   Tests knowledge ingestion, datasets, retrieval metrics, benchmarks, and agent-oriented context.

3. **Dark Factory**
   Tests application architecture, product scope, technical gaps, MVP status, and deployment readiness.

Together, these cover most of the ontology needed for the rest of the portfolio.

---

# 18. Delivery phases

## Phase 0 — Vault constitution

Create:

* vault charter;
* OKF profile;
* type taxonomy;
* naming policy;
* source hierarchy;
* trust model;
* verification process;
* lifecycle vocabulary.

## Phase 1 — Source inventory

Create a complete machine-readable manifest of documentation for the three pilot projects.

Deliverables:

```text
source-manifest.yaml
duplicate-report.md
classification-report.md
canonical-candidate-report.md
documentation-gap-report.md
```

## Phase 2 — Canonical project bundles

Generate:

* `project.md`;
* `status.md`;
* `architecture.md`;
* components;
* decisions;
* validations;
* risks;
* references;
* indexes.

## Phase 3 — Portfolio layer

Generate:

* portfolio overview;
* maturity matrix;
* shared capability map;
* technology inventory;
* dependency graph;
* strategic priority view.

## Phase 4 — Automation

Implement:

* incremental source scanning;
* change detection;
* regeneration;
* link validation;
* metadata validation;
* index generation;
* freshness alerts;
* contradiction detection.

## Phase 5 — Agent integration

Create operating instructions for:

* Claude Code;
* Codex;
* Gemini;
* local agents;
* NotebookLM exports;
* repository assistants.

## Phase 6 — Continuous governance

Add:

* review queues;
* canonical promotion;
* stale-note management;
* supersession handling;
* project onboarding;
* project archiving;
* monthly portfolio review.

---

# 19. Suggested repository design

The vault itself should live in Git. OKF specifically recommends Git repositories because they provide history, attribution, line-by-line diffs, and review workflows. ([GitHub][1])

```text
project-atlas/
├── vault/
├── schemas/
├── templates/
├── scripts/
├── tests/
├── config/
├── imports/
├── reports/
├── AGENTS.md
├── CLAUDE.md
├── README.md
└── pyproject.toml
```

Suggested tooling:

```text
Python
├── source discovery
├── frontmatter parsing
├── document classification
├── OKF generation
├── link validation
├── quality gates
└── reporting

Obsidian
├── human navigation
├── graph exploration
├── editing
└── review

Git
├── history
├── diffs
├── approvals
└── rollback

Optional local AI
├── extraction
├── classification
├── summarization
└── contradiction analysis
```

---

# 20. Strong recommendation

Build this as an **OKF-compliant portfolio knowledge system that happens to use Obsidian**, rather than an Obsidian vault with some OKF frontmatter.

That distinction protects the architecture from becoming dependent on:

* a particular Obsidian plugin;
* proprietary query syntax;
* one AI provider;
* one operating system;
* one storage provider;
* one repository host.

OKF is explicitly vendor-neutral and can be consumed by Obsidian, static sites, search indexes, graph viewers, and AI agents. ([GitHub][2])

## Proposed product statement

> **Project Atlas converts fragmented project documentation into a source-backed, continuously maintained Open Knowledge Format portfolio that humans and AI agents can navigate, verify, and act upon.**

The strongest next deliverable would be a **formal Project Requirements Prompt and vault specification**, including the complete taxonomy, frontmatter schemas, templates, ingestion workflow, quality gates, and pilot-project rollout. 🚀

[1]: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md "knowledge-catalog/okf/SPEC.md at main · GoogleCloudPlatform/knowledge-catalog · GitHub"
[2]: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/README.md "knowledge-catalog/okf/README.md at main · GoogleCloudPlatform/knowledge-catalog · GitHub"
