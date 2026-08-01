# AGENTS.md — Project Atlas

Guidance for AI coding agents working in this repository. Written for a reader who knows nothing about the project.

## Project overview

**Project Atlas** is a planned local-first "project knowledge compiler". It will scan approved documentation sources, classify and normalize them, extract evidence-backed concepts, and generate a structured Obsidian vault following an internal **Open Knowledge Format (OKF)** profile. The output is both a human-readable portfolio operating system and an agent-readable knowledge substrate.

Core principles (from the design docs):

- **No claim without a traceable source** — every generated concept must carry provenance back to its sources.
- **Three-layer vault model** — Layer A: imported source evidence; Layer B: canonical OKF concept notes; Layer C: synthesized portfolio intelligence. Generated summaries must never be confused with original evidence.
- **Determinism and offline operation** — the fixture pipeline must produce byte-identical output on repeated runs and work without internet access.
- **Human-edit preservation** — generated regions of notes are delimited with markers; regeneration must preserve protected human sections byte-for-byte and fail closed on malformed markers.
- **No subjective trust scores** — store objective signals (source, author, verification, timestamps, freshness, lifecycle) instead.

## Current repository state

**WP-001 (roadmap Phase 0, backlog Epics A and B) is implemented.** The repository now contains an installable Python 3.12+ package alongside the planning documents in `docs/`:

- `pyproject.toml` — package `project-atlas` (src layout), `atlas` console script, pytest/ruff/mypy configuration.
- `src/project_atlas/` — `cli.py` (`version`, `init`), `config.py` (TOML config loading), `logging.py` (structured console/JSON logging), `scaffold.py` (deterministic vault scaffold, FR-001), `schema.py` (JSON-schema validation, B-007), `domain/` (Pydantic models: `SourceRecord`, `ConceptRecord`, `Claim`, `ProvenanceReference`, `ConflictRecord`, `Relationship`, `ValidationFinding`, plus controlled vocabularies), `schemas/` (six JSON schemas, package data).
- `tests/unit/` and `tests/integration/` — 54 tests.
- `.github/workflows/ci.yml` — ruff, mypy, pytest, CLI smoke.
- `WORKLOG.md` — execution log per work package; `docs/adr/` — architectural decision records.

Planning documents (authoritative specification):

- `docs/plan.md` — project concept: vault architecture, OKF taxonomy, source-of-truth model, ingestion pipeline, quality gates, delivery phases, suggested repository design.
- `docs/prp.md` — Product Requirements Prompt: functional requirements (FR-001 to FR-015), non-functional requirements (NFR-001 to NFR-007), MVP boundary, success metrics, final acceptance commands.
- `docs/acceptance-test.md` — acceptance tests AT-001 to AT-020.
- `docs/backlog.md` — executable backlog, Epics A through K (repository foundation, domain model, discovery, parsing, classification, generation, human-safe updates, validation, portfolio intelligence, incremental operation, pilot onboarding).
- `docs/implementation-roadmap.md` — Phases 0 through 9 with deliverables and exit gates.

When implementing, treat these documents as the authoritative specification. The backlog checkboxes in `docs/backlog.md` track execution progress — keep them updated as work is completed.

## Technology stack

- **Language:** Python 3.12+, packaged with a `src/project_atlas` layout and a `pyproject.toml`. Core dependencies: `pydantic` v2, `PyYAML`, `jsonschema`.
- **CLI:** an `atlas` command. Implemented: `version`, `init`. Planned: `discover`, `ingest`, `build-indexes`, `validate`.
- **Testing:** `pytest` with unit and integration tests under `tests/`; fixture corpora under `tests/fixtures` for the three pilot projects (Nebula Control Platform, Black Agency OS, Dark Factory) are planned (backlog Epic K).
- **Linting/typing:** `ruff` and `mypy` (strict mode), configured in `pyproject.toml`.
- **Schemas:** JSON schemas validating domain records (`SourceRecord`, `ConceptRecord`, `Claim`, `ProvenanceReference`, `ConflictRecord`, `ValidationFinding`), shipped as package data under `src/project_atlas/schemas/` (ADR-001) and exercised via `project_atlas.schema.validate_record`.
- **Logging:** structured logging in `project_atlas.logging` (console and JSON formats, stderr only).
- **CI:** `.github/workflows/ci.yml` runs ruff, mypy, pytest, and a CLI smoke test.
- **Output format:** plain Markdown with YAML frontmatter (OKF profile), readable without Obsidian (NFR-003).

## Build, test, and acceptance commands

Working today (use the project venv, e.g. `.venv/bin/python`, or any environment with `pip install -e ".[dev]"`):

```bash
python -m pytest
python -m ruff check .
python -m mypy src
atlas --help
atlas version
atlas init --output .tmp/vault [--dry-run]
```

From `docs/prp.md` (final acceptance) — these commands define MVP completion; `discover`, `ingest`, `build-indexes`, and `validate` are not implemented yet:

```bash
python -m pytest
atlas init --output .tmp/vault
atlas discover --source tests/fixtures --output .tmp/manifest.json
atlas ingest --manifest .tmp/manifest.json --vault .tmp/vault
atlas build-indexes --vault .tmp/vault
atlas validate --vault .tmp/vault
```

## Code and design conventions (from the specification)

When implementing, follow these rules from the docs:

- **Deterministic rules first.** Deterministic classification must run before any optional model-assisted classification (FR-004); ambiguous documents must classify as `unknown` rather than an invented type (AT-006).
- **Fail closed on safety issues.** Unbalanced protection markers must abort regeneration with a non-zero exit and leave the file unmodified (AT-011). Path traversal in source paths must never cause writes outside the vault root (AT-013).
- **Secrets handling.** Likely credentials must be detected and excluded or redacted before any generated output or log is written (NFR-004, AT-014).
- **Atomic file writes** for generated notes (backlog F-007).
- **Streaming hashing** — SHA-256 hashing must not load all content into memory; a 10,000-file corpus must be handled incrementally (NFR-005).
- **Explicit interfaces** for parsers, classifiers, generators, validators, and provider integrations (NFR-006). Provider adapters are optional (roadmap Phase 9): disabling them must leave the MVP functional, and model output must never bypass provenance or validation.
- **Incremental refresh** — repeated runs must process only changed/added/removed sources and preserve stable IDs (FR-013).

## Testing strategy

- Acceptance tests AT-001 to AT-020 in `docs/acceptance-test.md` define the required behaviors; each should map to executable tests.
- Golden-file tests are specified for human-safe regeneration (backlog G-005).
- Expected manifests and expected generated vaults are part of the pilot fixtures (backlog K-004, K-005).
- Key invariants to test: 100% repeat-run idempotency for unchanged sources, 0 protected-region modifications, 100% link resolution, 0 secrets in output.

## Documentation conventions

- All documentation is written in **English**; keep new docs, comments, and commit messages in English.
- Design docs use requirement IDs (FR-xxx, NFR-xxx, AT-xxx) and backlog IDs (Epic letter + number, e.g. `C-004`). Reference these IDs in code comments and tests where relevant so traceability to the spec is preserved.

## Notes for agents

- The repository foundation exists; do not recreate it. Add new modules under `src/project_atlas/` and keep the strict ruff/mypy gates green.
- The vault structure described in `docs/plan.md` section 3 (directories like `00-system/`, `01-portfolio/`, `projects/`, `templates/`) is the *output* the tool generates, not the layout of this repository.
