# Implementation Roadmap

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
