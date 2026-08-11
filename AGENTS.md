# AGENTS.md — Project Atlas

Guidance for AI coding agents working in this repository. Written for a reader who knows nothing about the project.

## Project overview

**Project Atlas** is a local-first, source-backed "project knowledge compiler". It scans approved documentation sources, classifies and normalizes them, extracts evidence-backed concepts, and generates a structured Obsidian vault following an internal **Open Knowledge Format (OKF)** profile. The output is both a human-readable portfolio operating system and an agent-readable knowledge substrate.

Core principles (from `docs/plan.md` and `docs/prp.md`):

- **No claim without a traceable source** — every generated concept must carry provenance back to its sources.
- **Three-layer vault model** — Layer A: imported source evidence; Layer B: canonical OKF concept notes; Layer C: synthesized portfolio intelligence. Generated summaries must never be confused with original evidence.
- **Determinism and offline operation** — the fixture pipeline must produce byte-identical output on repeated runs and work without internet access.
- **Human-edit preservation** — generated regions of notes are delimited with markers; regeneration must preserve protected human sections byte-for-byte and fail closed on malformed markers.
- **No subjective trust scores** — store objective signals (source, author, verification, timestamps, freshness, lifecycle) instead.

## Current repository state

The repository has grown well beyond the original WP-001 foundation, and beyond
the original Core-only pipeline described below. As of `main` at the current
checkout, the following are implemented:

- Full Core pipeline: `atlas discover` → `atlas ingest` → `atlas build-indexes` → `atlas validate`.
- `src/project_atlas/` — installable Python 3.12+ package (src layout). It now
  spans 130+ modules: the original CLI/config/logging/scaffold/discovery/
  ingestion/indexing/validation/secrets/knowledge-compilation/semantic-
  compilation/lineage/domain surface, **plus** a 2.1 live productization
  layer added on top — `api_server.py` (local-bind HTTP API), `mcp_server.py`
  (read-only MCP), `agentos.py`/`authz.py`/`scheduler_live.py`/`autonomy_l3.py`
  (Agent OS), `chatgpt_bridge.py`/`chatgpt_capture.py` (ChatGPT integration),
  `obs_live.py`/`obs_perf.py`/`ops_receipts.py` (observability), `doctor.py`
  (productization), and modules tied to Atlas 2.2 knowledge-intelligence
  packages (`hybrid_retrieval.py`, `context_pack*.py`, `kci.py`, etc.) whose
  package documentation under `docs/atlas-2.2/` began as PREP. A module's
  presence in `src/` is not itself evidence of PREP status or of
  production-wiring in either direction — check current code and
  `docs/atlas-2.2/README.md`'s gate state before asserting either.
  Do not treat this list as exhaustive or as a maturity claim — for
  capability-by-capability maturity, read
  `docs/atlas-2.1/FEATURE-MATURITY-MATRIX.md`, not this file.
- `apps/web/` — a separate web app (Vite + React + TypeScript, Playwright
  e2e under `apps/web/e2e/`) consuming the live API/MCP surfaces.
- `integrations/chatgpt-atlas/` — a standalone read-only ChatGPT MCP gateway
  (own `server.py`, tests, and README), separate from the in-package
  `chatgpt_bridge.py`.
- `src/atlas_contracts/` — shared subsystem contracts for agent events, event packages, provenance, receipts, identity, and versions.
- `atlas-vault-documentation/` — separate sibling deliverable that implements the governed agent documentation skill and control plane (`AS-CTRL-001`, `AS-SKILL-001`). It has its own tests, scripts, schemas, references, and skill manifest; it is intentionally excluded from the main package's ruff/mypy scope.
- A security remediation wave has landed on `main` (provenance/trusted-exec,
  path/secrets/API-auth hardening, Windows process handling, dependency
  integrity, log redaction). This is internal multi-agent validation, not an
  external security certification — none has been obtained. See
  `docs/security/REGRESSION-SUITE-SEED.md`.
- A Windows productization CLI (install / onboarding / `atlas doctor`) has
  landed — see `docs/productization/install/` and `docs/productization/onboard/`.
- `tests/unit/` and `tests/integration/` — run `python -m pytest` for the
  current count; do not carry forward any specific number as current without
  re-running (see `WORKLOG.md` tail for the last logged evidence run).
- `.github/workflows/ci.yml` — ruff, mypy, pytest, CLI smoke.
- `.github/workflows/atlas-documentation-gate.yml` — receipt-gated documentation gate triggered manually.
- `WORKLOG.md` — execution log per work package; `docs/adr/` — architectural decision records.

STATUS AT LAST DOC REALIGNMENT: `ATLAS_2_1_RELEASE_CERTIFIED = NO` (see
`docs/atlas-2.1/KNOWN-GAPS.md`). VERIFY AGAINST CURRENT MAIN before relying
on this gate value — it moves as work lands.

Atlas 2.2 (`docs/atlas-2.2/`) contains extensive PREP contracts and may also
contain newer runtime implementation as `main` advances. PREP documents are
never evidence of implementation, and a runtime module is not "PREP" merely
because its originating 2.2 package documentation began as PREP. Consult
`docs/atlas-2.2/README.md` plus current runtime/code and gate state
(`docs/atlas-2.2/PREP-STATUS.md`) before asserting a 2.2 capability is, or
is not, implemented.

Planning documents (authoritative specification):

- `docs/plan.md` — project concept: vault architecture, OKF taxonomy, source-of-truth model, ingestion pipeline, quality gates, delivery phases, suggested repository design.
- `docs/prp.md` — Product Requirements Prompt: functional requirements (FR-001 to FR-015), non-functional requirements (NFR-001 to NFR-007), MVP boundary, success metrics, final acceptance commands.
- `docs/acceptance-test.md` — acceptance tests AT-001 to AT-020.
- `docs/backlog.md` — executable backlog, Epics A through K and cross-cutting Core slice.
- `docs/implementation-roadmap.md` — Phases 0 through 9 with deliverables and exit gates.
- `docs/master-roadmap.md` — program-level work-package status and strategic phases.
- `docs/adr/` — architectural decision records.

When implementing, treat these documents as the authoritative specification. The backlog checkboxes in `docs/backlog.md` track execution progress — keep them updated as work is completed.

## Code organization

### Core package — `src/project_atlas/`

| Module | Purpose |
|--------|---------|
| `cli.py` | `atlas` argparse entry point; dispatches all commands; exit codes 0/1/2. |
| `config.py` | TOML config loading via stdlib `tomllib`; defaults → `[tool.atlas]` → explicit file. |
| `scaffold.py` | `atlas init`; deterministic vault skeleton with path-safety checks. |
| `discovery.py` | `atlas discover`; streaming SHA-256, project markers, agent-event inventory. |
| `ingestion.py` | `atlas ingest`; manifest validation, source ingestion, agent-event quarantine, identity locks, write plan. |
| `indexes.py` | `atlas build-indexes`. |
| `validation.py` | `atlas validate`; link checking, OKF frontmatter, provenance hash validation. |
| `knowledge_compiler.py` | `AS-CORE-003`: claim extraction, authority, conflicts, reviews, lifecycle. |
| `semantic_compiler.py` | `AS-CORE-002`: project record compilation, OKF rendering. |
| `lineage.py` | `AS-ID-001`: source-lineage identity, v1→v2 registry migration. |
| `source_identity.py` | UUID validation, lineage ID derivation, project identity locks. |
| `schema.py` | JSON schema loading/validation via `importlib.resources`. |
| `secrets.py` | Conservative content-based secret scanning. |
| `logging.py` | Structured stderr-only logging. |
| `okf_renderer.py` | OKF note rendering helpers. |
| `retrieval.py` | `AS-RET-001`: read-only deterministic lexical exact/prefix retrieval. |
| `domain/` | Pydantic v2 domain models and controlled vocabularies. Import from `project_atlas.domain`, not submodules. |
| `schemas/` | Shipped JSON schemas (package data). |

### Shared contracts — `src/atlas_contracts/`

| Module | Purpose |
|--------|---------|
| `agent_event.py` | `AgentEvent`, `EventType`, `SkillBinding`, `VaultIdentity`. |
| `event_package.py` | `EventPackage`, `EventPackageInventory`, loading and inspection. |
| `provenance.py` | `ProvenanceRecord`. |
| `receipts.py` | `ReceiptReference`, `PipelineState`. |
| `identity.py` | `safe_relative_component` path guard. |
| `versions.py` | ID/hash patterns. |
| `schemas/` | Shipped JSON schemas for agent events, event packages, provenance, receipts. |

### Governed documentation skill / control plane — `atlas-vault-documentation/`

This is a **separate sibling deliverable** with its own tooling and tests. It is **not** part of the `project-atlas` package and is excluded from the main ruff/mypy scope (`pyproject.toml` includes only `src/**/*.py` and `tests/**/*.py`).

- `agent_control/` — universal Atlas agent control plane (`AS-CTRL-001`): `bootstrap`, `preflight`, `postflight`, `session`, `receipt_gate`, `skill_loader`, `protected_paths`, `readiness`, `adapter_registry`, `capability`, `vault_identity`.
- `scripts/` — helper scripts including `capture_event.py`, `atlas_agent.py` (CLI), `atlas_config.py`, `document_work.py`, `validate_agent_session.py`, etc.
- `tests/` — control-plane test suite (146 tests passing as recorded in `WORKLOG.md`).
- `references/` — governance contracts (event taxonomy, schemas, integration rules).
- `schemas/` — control-plane JSON schemas.
- `skill/SKILL.md` — canonical executable governance contract for managed Atlas agents.
- `config/agent-readiness.yaml` — adapter registry with skill version/SHA-256 and rehearsal status.

The canonical skill lifecycle is: `bootstrap → preflight → session-start → work milestones → validation → completion → postflight → receipt → close`.

## Technology stack

- **Language:** Python 3.12+, packaged with a `src/project_atlas` layout and `pyproject.toml`.
- **Core dependencies:** `pydantic` v2, `PyYAML`, `jsonschema`.
- **Dev dependencies:** `pytest`, `ruff`, `mypy`, `types-PyYAML`.
- **Build:** `setuptools>=68` with `src` layout; console script `atlas = "project_atlas.cli:main"`.
- **CLI:** `atlas` command with subcommands `version`, `init`, `discover`, `ingest`, `build-indexes`, `validate`.
- **Linting/typing:** `ruff` and `mypy` (strict mode) configured in `pyproject.toml`; scope is limited to `src/**/*.py` and `tests/**/*.py`.
- **Schemas:** JSON schemas validating domain records and contracts, shipped as package data under `src/project_atlas/schemas/` and `src/atlas_contracts/schemas/` and exercised via `project_atlas.schema.validate_record`.
- **Logging:** structured logging in `project_atlas.logging` (console and JSON formats, stderr only).
- **Output format:** plain Markdown with YAML frontmatter (OKF profile), readable without Obsidian (NFR-003).

## Build, test, and acceptance commands

Use the project venv (`.venv/bin/python`) or any environment with `pip install -e ".[dev]"`.

Standard quality gates:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest -m integration
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
```

CLI smoke tests:

```bash
atlas --help
atlas version
atlas init --output .tmp/atlas-vault --dry-run
atlas init --output .tmp/atlas-vault
```

Full Core pipeline:

```bash
atlas init --output .tmp/vault
atlas discover --source <project-root> --output .tmp/manifest.json
atlas ingest --manifest .tmp/manifest.json --vault .tmp/vault
atlas build-indexes --vault .tmp/vault
atlas validate --vault .tmp/vault
```

Governed agent session (control plane):

```bash
python atlas-vault-documentation/scripts/atlas_agent.py doctor --project-root . --json
python atlas-vault-documentation/scripts/atlas_agent.py run --agent generic --project-root . --task-id AS-CTRL-001 -- <command>
```

## Code and design conventions (from the specification)

When implementing, follow these rules from the specification:

- **Deterministic rules first.** Deterministic classification must run before any optional model-assisted classification (FR-004); ambiguous documents must classify as `unknown` rather than an invented type (AT-006).
- **Fail closed on safety issues.** Unbalanced protection markers must abort regeneration with a non-zero exit and leave the file unmodified (AT-011). Path traversal in source paths must never cause writes outside the vault root (AT-013).
- **Secrets handling.** Likely credentials must be detected and excluded or redacted before any generated output or log is written (NFR-004, AT-014).
- **Atomic file writes** for generated notes — temp file in target directory, then `os.replace`.
- **Streaming hashing** — SHA-256 hashing must not load all content into memory; a 10,000-file corpus must be handled incrementally (NFR-005).
- **Explicit interfaces** for parsers, classifiers, generators, validators, and provider integrations (NFR-006). Provider adapters are optional (roadmap Phase 9): disabling them must leave the MVP functional, and model output must never bypass provenance or validation.
- **Incremental refresh** — repeated runs must process only changed/added/removed sources and preserve stable IDs (FR-013).
- **Deterministic output** — no wall-clock timestamps in generated content (NFR-001); JSON uses `sort_keys=True`.
- **Domain model imports** — import from `project_atlas.domain`, not submodules; `domain/__init__.py` enforces the public surface.
- **Requirement traceability** — reference requirement/backlog IDs (`FR-xxx`, `NFR-xxx`, `AT-xxx`, `AS-xxx`, `B-xxx`) in code comments and tests.

## Testing strategy

- Acceptance tests AT-001 to AT-020 in `docs/acceptance-test.md` define required behaviors; each should map to executable tests.
- Golden-file tests are specified for human-safe regeneration (backlog G-005).
- Expected manifests and expected generated vaults are part of the pilot fixtures (backlog K-004, K-005).
- Key invariants to test: 100% repeat-run idempotency for unchanged sources, 0 protected-region modifications, 100% link resolution, 0 secrets in output.
- `tests/unit/` covers contracts, config, domain models, schema, scaffold, knowledge compiler, semantic models, source identity, OKF conformance.
- `tests/integration/` covers CLI smoke, ingestion security, agent-event ingestion, Core vertical slice, claims/authority/conflicts, semantic lifecycle, OKF public conformance.
- The control-plane suite in `atlas-vault-documentation/tests/` is run separately (its own `conftest.py` and pytest invocation).

## Security considerations

- **Path traversal protection** (AT-013): output paths are resolved and rejected up front (filesystem root, home dir, existing file, non-empty dir), and every write is re-checked with `is_relative_to(resolved)` before touching disk. `_inside()` in `ingestion.py` and `_source_path()` reject absolute paths, backslashes, and `..`.
- **Secret detection and redaction**: `project_atlas.secrets.scan_text` scans for private keys, bearer tokens, API keys, passwords, connection strings, AWS keys. Findings return metadata only, never matched content. Sources with secret findings are quarantined during ingestion; agent-event summaries are redacted before persistence.
- **Agent-event boundary**: Vault identity and trusted skill policy are required for event ingestion. Hash mismatches, wrong vault identity, skill mismatch, pending pipeline, malformed packages, and conflicting event IDs are quarantined before canonical projection.
- **Protected paths**: agents must not directly mutate `projects/`, `routing/state/`, `routing/receipts/`, `relationships/` (defined in `atlas-vault-documentation/agent_control/protected_paths.py`).
- **Sensitive file exclusions**: `.gitignore` excludes `.env`, credentials, keys, certs; `discovery.py` excludes sensitive filenames and unsupported formats.

## Documentation conventions

- All documentation is written in **English**; keep new docs, comments, and commit messages in English.
- Design docs use requirement IDs (`FR-xxx`, `NFR-xxx`, `AT-xxx`) and backlog IDs (Epic letter + number, e.g. `C-004`). Reference these IDs in code comments and tests where relevant so traceability to the spec is preserved.

## Notes for agents

- The repository foundation and a substantial Core vertical slice exist; do not recreate it. Add new modules under `src/project_atlas/` and keep the strict ruff/mypy gates green.
- The vault structure described in `docs/plan.md` section 3 (directories like `00-system/`, `01-portfolio/`, `projects/`, `templates/`) is the *output* the tool generates, not the layout of this repository.
- `atlas-vault-documentation/` is a sibling deliverable, not part of the `project-atlas` package. Do not import it from Core code, and do not expect the main ruff/mypy config to cover it.
- For governed work in this repository, follow `AGENT-BOOTSTRAP.md` and the canonical skill in `atlas-vault-documentation/skill/SKILL.md`. Use `atlas_agent.py` for session lifecycle management and `document_work.py`/`capture_event.py` for recording meaningful work.
- Update `docs/backlog.md` checkboxes and append to `WORKLOG.md` as work packages complete.
