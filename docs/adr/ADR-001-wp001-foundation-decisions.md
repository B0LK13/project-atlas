# ADR-001 — WP-001 foundation decisions

**Status:** accepted
**Date:** 2026-08-01
**Scope:** WP-001 (backlog Epics A and B, roadmap Phase 0)

## Context

WP-001 required an installable package, CLI, configuration, domain models,
JSON schemas, structured logging, and a deterministic, fail-closed
`atlas init`. Two decisions deviate from a naive reading of the planning
documents and are recorded here.

## Decisions

### 1. JSON schemas ship as package data, not as a top-level `schemas/` directory

`docs/plan.md` section 19 suggests a repository layout with a top-level
`schemas/` directory. WP-001 instead places the canonical schemas in
`src/project_atlas/schemas/*.json` and loads them via
`importlib.resources` (`project_atlas.schema`).

Rationale: schema validation (B-007) must work from an installed wheel
without depending on a repository checkout, and a single canonical copy
avoids drift between a repo-level and a package-level duplicate. The
schemas remain plain JSON files and can be exported later if external
tooling needs them.

### 2. Scaffold generation embeds no wall-clock timestamps

NFR-001 requires byte-identical output across repeated runs, while
NFR-007 requires generation metadata in every generated file. For
`atlas init` these conflict if `generated.at` is populated with the
current time. The scaffold therefore records `generated.by:
agent:atlas-init` and omits timestamp fields entirely; later phases
(ingestion, index generation) that maintain state can introduce explicit,
test-controlled timestamps where determinism is defined to exclude them
(NFR-001 already excludes "explicitly allowed timestamps").

## Consequences

- `atlas init` output is byte-identical across runs and machines on the
  same platform; this is verified by
  `test_scaffold_output_is_byte_identical_across_runs`.
- The domain JSON Schemas and the Pydantic models are maintained side by
  side; `tests/unit/test_schema.py` validates sample model dumps against
  every shipped schema to keep them in lockstep.
