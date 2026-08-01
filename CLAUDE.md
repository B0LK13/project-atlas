# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Project Atlas is a local-first "project knowledge compiler": it scans approved
documentation sources and generates a structured Obsidian vault following an
internal Open Knowledge Format (OKF) profile — evidence-backed, offline,
deterministic. See `AGENTS.md` for the full principles and core narrative
(no claim without a traceable source, three-layer vault model, human-edit
preservation, no subjective trust scores) — this file focuses on commands and
architecture, not repeating that narrative.

Only WP-001 (Phase 0, backlog Epics A and B) is implemented: an installable
Python package with CLI, config, domain model, and schema validation. The
`discover`/`ingest`/`build-indexes`/`validate` pipeline is not built yet.
Check `WORKLOG.md` (tail) for the current work-package status and
`docs/backlog.md` for what's checked off.

## Commands

```bash
pip install -e ".[dev]"                                   # editable install with dev deps

python -m pytest                                          # full test suite
python -m pytest tests/unit/test_scaffold.py::test_name    # single test
python -m pytest -k pattern                                 # by keyword
python -m pytest -m integration                             # integration-marked tests only

python -m ruff check .                                      # lint (src/ and tests/ only)
python -m mypy src                                           # strict type check

atlas --help
atlas version
atlas init --output <dir> [--dry-run]                       # create a vault scaffold
```

`.github/workflows/ci.yml` is the authoritative gate sequence: ruff → mypy →
pytest → CLI smoke test (`atlas init --dry-run`, then a real `atlas init`,
asserting `index.md` and `00-system/vault-charter.md` exist).

## Architecture

**Package layout** (`src/project_atlas/`, src-layout):

- `cli.py` — argparse-based `atlas` entry point; dispatches to `config.py`
  and `scaffold.py`. Exit codes: `0` success, `1` operational error, `2`
  argparse usage error.
- `config.py` — TOML config loading via stdlib `tomllib`, precedence
  defaults → `[tool.atlas]` in `pyproject.toml` → explicit `--config` file.
  All fields default safely; the CLI works with zero configuration.
- `scaffold.py` — `atlas init` (FR-001/AT-001): builds the vault skeleton
  described in `docs/plan.md` §3. **The directory structure this module
  writes (`00-system/`, `projects/`, `sources/`, etc.) is the tool's
  *output*, not this repository's own layout** — a common point of
  confusion.
- `domain/` — Pydantic v2 models (`SourceRecord`, `ConceptRecord`, `Claim`,
  `ProvenanceReference`, `ConflictRecord`, `Relationship`,
  `ValidationFinding`) plus controlled vocabularies (`vocabulary.py`:
  concept types, lifecycle/maturity/knowledge-state enums). Import from the
  package root (`from project_atlas.domain import ...`), not submodules —
  enforced by `domain/__init__.py`'s docstring and `__all__`.
- `schemas/` — one JSON Schema per domain record, shipped as package data
  (`importlib.resources`) so validation works from an installed wheel
  without a repo checkout (ADR-001). Checked via
  `project_atlas.schema.validate_record(record, kind)`, which keeps the
  Pydantic models and the published JSON contract in lockstep.
- `logging.py` — structured logging to **stderr only** (so vault content
  printed to stdout is never interleaved with logs); `console` or `json`
  formatter, loggers namespaced `project_atlas.<module>`.

**Conventions that carry across modules** (established in `scaffold.py`,
expected to hold for future `discover`/`ingest`/etc.):

- Deterministic output — no wall-clock timestamps in generated content
  (NFR-001); metadata records `generated.by` only, never `generated.at`
  (ADR-001 §2).
- Fail-closed path safety — output paths are resolved and rejected up front
  (filesystem root, home dir, existing file, non-empty dir), and every
  individual write is re-checked with `is_relative_to(resolved)` before
  touching disk (defence in depth against path traversal, AT-013).
- Atomic writes — temp file in the target directory, then `os.replace`.
- Docs-as-spec traceability — code and tests reference requirement/backlog
  IDs (`FR-xxx`, `NFR-xxx`, `AT-xxx`, `B-xxx`, ...) defined in `docs/`
  (`plan.md`, `prp.md`, `acceptance-test.md`, `backlog.md`,
  `implementation-roadmap.md`, `adr/`). Update `docs/backlog.md` checkboxes
  as work completes; log each work package's plan/commands/results in
  `WORKLOG.md`.

**Out of scope for the above commands**: `atlas-vault-documentation/` and
`AGENT-BOOTSTRAP.md` implement a separate "governed agent control plane"
(session receipts, skill hashing, `atlas_agent.py doctor`/`run`) with its
own tooling. `pyproject.toml`'s ruff config explicitly excludes it from the
main package's lint/type scope — it's a sibling deliverable, not part of
`project_atlas`.
