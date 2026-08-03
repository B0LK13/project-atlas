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

The certified Core pipeline is implemented: `discover` → `ingest` →
`build-indexes` → `validate`. The repository also contains shared Atlas
contracts (`src/atlas_contracts/`) and the governed agent control-plane
sibling deliverable (`atlas-vault-documentation/`). Check `WORKLOG.md`
(tail) for the current work-package status and `docs/backlog.md` for
what's checked off.

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
atlas discover --source <project-root> --output <manifest.json>
atlas ingest --manifest <manifest.json> --vault <vault-dir>
atlas build-indexes --vault <vault-dir>
atlas validate --vault <vault-dir>
```

`.github/workflows/ci.yml` is the authoritative gate sequence: ruff → mypy →
pytest → CLI smoke test (`atlas init --dry-run`, then a real `atlas init`,
asserting `index.md` and `00-system/vault-charter.md` exist).

## Architecture

**Package layout** (`src/project_atlas/`, src-layout):

- `cli.py` — argparse-based `atlas` entry point; dispatches all commands.
  Exit codes: `0` success, `1` operational error, `2` argparse usage error.
- `config.py` — TOML config loading via stdlib `tomllib`, precedence
  defaults → `[tool.atlas]` in `pyproject.toml` → explicit `--config` file.
  All fields default safely; the CLI works with zero configuration.
- `scaffold.py` — `atlas init` (FR-001/AT-001): builds the vault skeleton
  described in `docs/plan.md` §3. **The directory structure this module
  writes (`00-system/`, `projects/`, `sources/`, etc.) is the tool's
  *output*, not this repository's own layout** — a common point of
  confusion.
- `discovery.py` — `atlas discover` (FR-002): recursive, streaming SHA-256
  inventory with default exclusions, configured include/exclude globs,
  sensitive filename protection, and `.atlas-project.yaml` markers.
- `ingestion.py` — `atlas ingest`: manifest validation, deterministic
  document classification, protected-region preservation, agent-event
  quarantine, and atomic canonical writes via a single `_promote(write_plan)`
  boundary.
- `indexes.py` — `atlas build-indexes` (FR-010): deterministic lexical
  indexes under `generated/indexes/`, rejects obsolete `indexes/` directory.
- `validation.py` — `atlas validate` (FR-012): link resolution, OKF
  frontmatter/schema checking, provenance hash validation, generated-index
  drift rejection.
- `retrieval.py` — read-only exact/prefix lookup over generated lexical
  indexes (AS-RET-001); never mutates the Vault.
- `knowledge_compiler.py` — deterministic claim extraction, authority
  precedence, conflict detection, review queue generation, and lifecycle
  transition enforcement (AS-CORE-003).
- `semantic_compiler.py` — project-record compilation and OKF Markdown
  rendering with protected human regions (AS-CORE-002).
- `lineage.py` — durable source-lineage identity, v1→v2 registry migration,
  and ambiguity fail-closed handling (AS-ID-001).
- `source_identity.py` — UUIDv4 project genesis, canonical path rules, and
  project identity locks.
- `okf_renderer.py` — OKF concept-note rendering helpers.
- `secrets.py` — conservative content-based secret scanning; returns
  metadata only, never matched content (NFR-004).
- `schema.py` — JSON Schema loading and validation via `importlib.resources`.
- `logging.py` — structured logging to **stderr only** (so vault content
  printed to stdout is never interleaved with logs); `console` or `json`
  formatter, loggers namespaced `project_atlas.<module>`.
- `domain/` — Pydantic v2 models and controlled vocabularies. Import from
  the package root (`from project_atlas.domain import ...`), not submodules
  — enforced by `domain/__init__.py`'s docstring and `__all__`.
- `schemas/` — JSON Schemas for domain records and contracts, shipped as
  package data so validation works from an installed wheel without a repo
  checkout (ADR-001).

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
own tooling. It is a sibling deliverable, not part of `project_atlas`.

`src/atlas_contracts/` are shared subsystem contracts (agent events, event
packages, provenance, receipts, identity, versions) used by both Core and
the control plane; they are part of the `project-atlas` package data.
