# Project Atlas

Project Atlas is a local-first, source-backed "project knowledge compiler" that
ingests approved documentation and evidence, extracts provenance-backed
concepts, and emits a deterministic, agent- and human-readable vault in an
Open Knowledge Format (OKF) profile.

This repository contains the Core implementation (Python 3.12+, src layout),
shared contracts, tests, CI, and a sibling governed documentation/control-plane
(subproject: `atlas-vault-documentation/`) that implements the agent skill and
session control surface.

Key principles
- No claim without traceable evidence: every generated concept references its
  originating source and provenance.
- Three-layer vault model: A (source evidence), B (canonical OKF concepts), C
  (synthesized portfolio intelligence). Generated summaries must preserve
  provenance and human-edited regions.
- Determinism & offline operation: byte-identical output for repeated runs; no
  Internet required for core functionality.
- Fail-closed safety: path safety, protected-region preservation, and secret
  quarantine are enforced.

Repository status (short)
- Core pipeline implemented: `discover` → `ingest` → `build-indexes` →
  `validate`.
- Tests: unit & integration tests present; documented passing results in
  `WORKLOG.md`.
- `atlas-vault-documentation/` is a sibling deliverable (governed agent
  control-plane) and is intentionally excluded from the main lint/type scope.

Quickstart (developer)
1. Create and activate Python 3.12 venv:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

2. Install editable package with dev dependencies:

```bash
pip install -e ".[dev]"
```

3. Run the test/lint gates locally:

```bash
python -m pytest
python -m ruff check .
python -m mypy src
```

4. Try CLI smoke commands:

```bash
atlas --help
atlas version
atlas init --output .tmp/atlas-vault --dry-run
atlas init --output .tmp/atlas-vault
```

Core CLI workflow
- atlas init --output <dir> [--dry-run]  # create deterministic vault scaffold
- atlas discover --source <project-root> --output <manifest.json>
- atlas ingest --manifest <manifest.json> --vault <vault-dir>
- atlas build-indexes --vault <vault-dir>
- atlas validate --vault <vault-dir>

Development notes & conventions
- Language: Python 3.12+, packaged in `src/project_atlas`.
- Domain models: Pydantic v2 models live under `src/project_atlas/domain/`.
  Import from `project_atlas.domain`, not submodules.
- JSON Schemas: shipped as package data under `src/project_atlas/schemas/` and
  `src/atlas_contracts/schemas/`.
- Determinism: generated content must avoid wall-clock timestamps and be
  reproducible across runs.
- Protected regions: human-edited sections in generated notes are preserved
  with explicit markers; regeneration fails closed on malformed markers.
- Secrets: conservative scanning quarantines suspect sources; matched content
  is never persisted in plaintext outputs.

Repository layout (high-level)
- src/project_atlas/        — Core package (cli, scaffold, discovery, ingest,
                             indexes, validation, compilers, utils)
- src/atlas_contracts/     — Shared contract models (agent events, receipts,
                             provenance, identity)
- atlas-vault-documentation/ — Governed agent control plane (separate
                             deliverable; own tests and skill manifest)
- docs/                    — authoritative planning and acceptance documents
- WORKLOG.md               — execution log and completion evidence
- .github/workflows/ci.yml — CI gate definitions

Governance, agents, and controlled workflows
- Governed agent sessions use `atlas-vault-documentation/scripts/atlas_agent.py`
  and the canonical skill (`atlas-vault-documentation/skill/SKILL.md`).
- The `AGENT-BOOTSTRAP.md` and `universal-directive.md` files define the
  bootstrap and evidence-first rules for autonomous agents working on this
  repository; agents must follow session lifecycle: bootstrap → preflight →
  session-start → work → validate → completion → postflight → receipt.
- The control plane is intentionally separate from the Core package and must
  not be imported into core runtime code.

Governance navigation
- `GOVERNANCE.md` — roles, certify/merge/baseline lifecycle, stop boundaries
- `CONTRIBUTING.md` — internal contribution and PR workflow
- `SECURITY.md` — vulnerability reporting limitations (no invented contacts)
- `SUPPORT.md` — support boundaries for this private repository
- `CODE_OF_CONDUCT.md` — conduct expectations and enforcement limitation
- `VERSIONING.md` / `RELEASING.md` — pre-1.0 version and release authorization
- `.github/ISSUE_TEMPLATE/` — structured issue forms (security → `SECURITY.md`)
- `docs/adr/ADR-006-github-repository-governance-baseline.md` — architecture

Contributing & branch policy
- Private repository model: currently maintained by the repository owner
  (`B0LK13`) and explicitly-authorized agents. No public contribution path is
  configured.
- Branch naming: `<type>/<AS-xxx-id>-<short-description>` (e.g.
  `fix/as-mvp-001-r1-tests`); architecture branches use `architecture/...`.
- All changes land via pull-request to `main`. Do not rewrite history, force
  push, or delete evidence. For governed work, include the evidence receipt in
  the PR description per `AGENT-BOOTSTRAP.md`.
- Live GitHub settings activation (required checks, approval restoration,
  CODEOWNERS enforcement) remains deferred until separately authorized and
  verified — see `GOVERNANCE.md`.

Security & vulnerability handling
- This pre-1.0 project has no published external private vulnerability intake.
  Do not open public issues with sensitive vulnerability details. Follow
  `SECURITY.md`.
- Confirm path-safety, secret detection, and protected-region enforcement before
  accepting changes that touch ingestion or generation code.

Where to find authoritative docs (read first)
- AGENTS.md — high-level agent guidance, architecture, and code map
- CLAUDE.md — commands, architecture summary, and developer recipes for agents
- docs/plan.md, docs/prp.md — planning, OKF profile, functional/acceptance
  requirements (PRP = product requirements prompt)
- docs/acceptance-test.md — acceptance tests (AT-001..AT-020)
- docs/backlog.md — executable backlog, Epics and checkboxes
- WORKLOG.md — completed work-package evidence and exact validation outputs
- atlas-vault-documentation/ — governed agent control surface and skill

Contact & owner
- Repository owner: B0LK13 (private maintainer). For sensitive matters follow
  the channels described in SECURITY.md.

License
- No license is published in this repository. Treat the code as private and
  follow the repository owner guidance for reuse.

—
This README synthesizes the authoritative documentation in this repository's
`docs/` and top-level governance files. For any non-trivial change follow the
evidence-first directives in `universal-directive.md` and the governed agent
bootstrap protocol in `AGENT-BOOTSTRAP.md`.
