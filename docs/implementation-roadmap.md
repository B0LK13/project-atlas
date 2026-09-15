# Implementation Roadmap

> **D-191 classification:** This document is a **historical input** (Phases 0–9)
> to Atlas 3.0. Canonical successor roadmap: `docs/atlas-3/MASTER-ROADMAP.md`.
> Do not erase this file. It remains evidence of how Atlas 1.x/2.x was delivered.

## Phase 0 — Foundation

### Objective

Create a validated repository foundation and domain model.

### Deliverables

- Python package scaffold
- configuration loader
- domain models
- JSON schemas
- CLI skeleton
- test harness
- logging conventions
- fixture conventions

### Exit gate

- package installs;
- CLI help works;
- schemas validate sample records;
- unit tests pass.

## Phase 1 — Discovery and manifests

### Objective

Inventory local project documentation safely and deterministically.

### Deliverables

- recursive discovery;
- include/exclude rules;
- file type detection;
- SHA-256 hashing;
- exact duplicate grouping;
- source manifest writer;
- discovery report.

### Exit gate

- fixture corpus produces expected manifest;
- duplicate fixtures are grouped;
- unchanged rerun is identical.

## Phase 2 — Markdown parsing and deterministic classification

### Objective

Understand baseline document structure without an LLM.

### Deliverables

- Markdown parser;
- frontmatter parser;
- heading extraction;
- link extraction;
- classification rules;
- confidence and method fields.

### Exit gate

- pilot fixtures classify above agreed precision;
- unknowns remain unknown;
- no unsupported assumptions.

## Phase 3 — Concept generation

### Objective

Generate source-backed project and source concepts.

### Deliverables

- project concept generator;
- source reference generator;
- component and decision candidate support;
- provenance serialization;
- stable IDs;
- templates.

### Exit gate

- each pilot project has a project bundle;
- every generated concept resolves to sources.

## Phase 4 — Human-safe regeneration

### Objective

Support repeated generation without damaging curated content.

### Deliverables

- protected-region parser;
- safe merge engine;
- malformed marker detection;
- regeneration tests.

### Exit gate

- protected human text remains byte-identical;
- malformed markers stop writes.

## Phase 5 — Indexes and portfolio reports

### Objective

Produce navigable project and portfolio views.

### Deliverables

- directory indexes;
- portfolio overview;
- maturity matrix;
- documentation coverage;
- stale knowledge report;
- conflict queue.

### Exit gate

- all internal links validate;
- every pilot project appears in portfolio views.

## Phase 6 — Validation framework

### Objective

Enforce structural, provenance, freshness, security, and completeness gates.

### Deliverables

- validator interface;
- built-in validators;
- JSON and Markdown reports;
- severity-based exit codes.

### Exit gate

- all acceptance fixtures produce expected findings;
- clean fixture vault passes.

## Phase 7 — Incremental updates

### Objective

Avoid full regeneration for unchanged corpora.

### Deliverables

- state cache;
- source change detection;
- impact mapping;
- removed-source handling;
- stable regeneration.

### Exit gate

- one changed source updates only expected outputs.

## Phase 8 — Context packs

### Objective

Generate bounded task-specific context.

### Deliverables

- context profile configuration;
- development pack;
- architecture pack;
- security pack;
- deployment pack;
- executive pack.

### Exit gate

- packs contain only relevant, traceable concepts;
- size limits are enforced.

## Phase 9 — Optional provider adapters

### Objective

Add model-assisted classification and extraction without weakening deterministic controls.

### Deliverables

- provider-neutral interface;
- mock provider;
- schema-constrained responses;
- offline fallback;
- audit logging.

### Exit gate

- disabling providers leaves the MVP functional;
- model output cannot bypass provenance or validation.
