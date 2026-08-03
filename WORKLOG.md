# WORKLOG — Project Atlas

Execution log for implementation work packages. Each entry records the plan,
exact commands run, exact results, deviations, and remaining risks.

---

## WP-001 — Repository Foundation and Domain Model

**Status:** complete
**Started:** 2026-08-01
**Backlog scope:** Epic A (A-001 to A-007) and Epic B (B-001 to B-007)
**Roadmap scope:** Phase 0 — Foundation

### Document deviations (read-before-editing list)

The assignment referenced `PRP.md`, `docs/ARCHITECTURE.md`,
`docs/OKF_PROFILE.md`, `docs/SOURCE_AUTHORITY_POLICY.md`,
`docs/QUALITY_GATES.md`, `IMPLEMENTATION_ROADMAP.md`, `ACCEPTANCE_TESTS.md`,
and `BACKLOG.md`. The repository instead contains:

- `docs/prp.md` (read; used as the requirements contract)
- `docs/plan.md` (read; contains the architecture, OKF profile guidance,
  source-of-truth model, and quality gates in sections 2-16)
- `docs/implementation-roadmap.md` (read; Phase 0 defines this work package)
- `docs/acceptance-test.md` (read; AT-001, AT-013 relevant to this package)
- `docs/backlog.md` (read; Epics A and B define this package)
- `AGENTS.md` (read)

No content was lost: the topics of the missing files are covered inside
`docs/plan.md` and `docs/prp.md`. All planning documents are preserved
unmodified except progress checkboxes in `docs/backlog.md`.

### Plan

1. Create Python 3.12+ package scaffold (`pyproject.toml`, src layout,
   package name `project-atlas`, CLI entry point `atlas`).
2. Implement structured JSON/console logging (`logging.py`).
3. Implement TOML configuration loading with safe defaults (`config.py`).
4. Implement Pydantic v2 domain models (`domain/`):
   `SourceRecord`, `ConceptRecord`, `Claim`, `ProvenanceReference`,
   `ConflictRecord`, relationship types, `ValidationFinding`, with the
   controlled vocabularies from `docs/plan.md` section 7
   (lifecycle, document lifecycle, maturity, review state, severity).
5. Supply JSON schemas for the domain records as package data
   (`src/project_atlas/schemas/`) and a validation helper
   (`src/project_atlas/schema.py`) using `jsonschema` (B-007).
6. Implement CLI (`cli.py`): `atlas --help`, `atlas version`,
   `atlas init --output <path> [--dry-run]`.
7. Implement vault scaffold generation (`scaffold.py`, FR-001 / AT-001):
   deterministic file set, unsafe-path and non-empty-directory rejection
   (fail closed, AT-013 posture), atomic file writes, `--dry-run`.
8. Configure pytest, ruff, mypy (strict) in `pyproject.toml`.
9. Add unit and integration tests covering the completion gate.
10. Add GitHub Actions CI workflow (A-006).
11. Record architectural deviations in `docs/adr/`.
12. Update `docs/backlog.md` checkboxes for completed Epic A/B items.

### Design decisions

- **argparse, no CLI framework dependency.** Keeps the dependency surface
  minimal and offline-friendly. Exit codes: 0 success, 1 operational error
  (unsafe path, non-empty target, write failure), 2 argparse usage error.
- **Schemas ship as package data** (`src/project_atlas/schemas/*.json`) so
  validation works from an installed wheel without depending on the
  repository checkout. Recorded in ADR-001.
- **Scaffold determinism:** generated files contain no wall-clock
  timestamps (NFR-001 byte-identical reruns). `generated.by` is recorded;
  timestamp fields are left to later ingestion phases. Recorded in ADR-001.
- **Config format:** TOML via stdlib `tomllib`; `atlas.toml` or
  `[tool.atlas]` in `pyproject.toml`; all fields optional with safe
  defaults.

### Validation commands (to be run and reported)

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
.venv/bin/atlas --help
.venv/bin/atlas version
.venv/bin/atlas init --output .tmp/atlas-vault --dry-run
.venv/bin/atlas init --output .tmp/atlas-vault
```

### Results

**Status: complete — all completion-gate criteria met.** (2026-08-01)

Environment: Python 3.12 in `.venv` (created with `python3.12 -m venv`;
deps `pydantic 2.13.4`, `jsonschema`, `PyYAML`, `pytest`, `ruff`,
`mypy`); package installed with `pip install -e ".[dev]"`.

Exact validation commands and results:

```
$ .venv/bin/python -m pytest
54 passed in 3.97s

$ .venv/bin/python -m ruff check .
All checks passed!                       (exit 0)

$ .venv/bin/python -m mypy src
Success: no issues found in 14 source files   (exit 0)

$ .venv/bin/atlas --help                 (exit 0; usage for version/init shown)
$ .venv/bin/atlas version
project-atlas 0.1.0                      (exit 0)

$ .venv/bin/atlas init --output .tmp/atlas-vault --dry-run
would create vault scaffold ... 31 directories, 29 files   (exit 0;
verified: nothing written to disk)

$ .venv/bin/atlas init --output .tmp/atlas-vault
created vault scaffold ... 31 directories, 29 files        (exit 0)
```

Completion-gate evidence:

- All new tests pass: 54 passed (unit + integration).
- Schemas load successfully: `test_schemas_load_and_are_valid`,
  `test_all_expected_schemas_available` (6 schemas, Draft 2020-12
  `check_schema` passes, cross-file `$ref` resolution verified).
- Core models reject invalid required fields: `test_rejects_missing_
  required_fields`, `test_rejects_invalid_sha256`,
  `test_excluded_requires_reason`, `test_claim_requires_provenance`,
  `test_requires_two_claims`, `test_rejects_unknown_lifecycle_value`,
  and others.
- CLI exit codes: `--help`/`version`/`init` return 0; init on non-empty
  or unsafe target returns 1 (verified on the CLI: rerun against the
  generated vault exits 1 with an error log); missing `--output` exits 2.
- Generated scaffold matches the directory contract:
  `test_scaffold_creates_expected_contract` (all FR-001 areas, system
  notes, templates) plus the manual `find` listing above; byte-identical
  reruns verified by `test_scaffold_output_is_byte_identical_across_runs`.

Test suite breakdown: 54 tests — domain models (20), schema validation
(7), config (7), logging (3), scaffold (9), CLI integration (8).

### Remaining risks

- Mid-session, a new top-level directory `atlas-vault-agent-documentation-skill/`
  appeared in the repository (a self-contained agent-documentation skill
  with its own PRP/roadmap/acceptance docs and Python scripts). It is a
  separate deliverable, not part of `project-atlas`; it was left
  unmodified, and the project's ruff scope was explicitly limited to
  `src/` and `tests/` (`include` in `pyproject.toml`) so its files do not
  break project gates. If it is meant to become part of this repository's
  scope, that decision and its tooling alignment belong to a future work
  package.
- `docs/backlog.md` Epic A/B checkboxes are now checked; no other
  planning document was modified.
- The CLI logs "loaded configuration" at INFO on every invocation when a
  config file is probed (stderr only; stdout stays clean). Consider
  demoting to DEBUG in WP-002 if it becomes noisy in pipelines.
- `atlas init` refuses all non-empty targets; an explicit `--force` /
  merge mode is intentionally deferred per the assignment.
- `DiscoveryConfig` fields (include/exclude globs, size limit) are
  defined but not yet consumed; WP-002 must wire them into discovery.
- JSON Schemas and Pydantic models are maintained as parallel
  definitions; `tests/unit/test_schema.py` keeps them consistent, but
  new model fields must always be mirrored in both places.
- CI workflow (`.github/workflows/ci.yml`) is written but not yet
  executed on a hosted runner; first push will validate it.

---

## AS-WP-001 — Deterministic Capture and Validation Hardening

**Status:** complete
**Started:** 2026-08-01
**Scope:** `atlas-vault-documentation/` subproject (universal documentation
transaction layer). Roadmap Phases 1-2 hardening; acceptance tests AS-002
to AS-008 and AS-018.

### Review findings (scripts as received)

`scripts/capture_event.py`:

- Already atomic (`tempfile.mkstemp` + `os.replace`, fsync) and refuses
  existing event files (exit 3) — AS-004 behavior present but untested.
- Path safety: `--event-id` is regex-validated; destination is checked
  with `ensure_descendant` — AS-018 posture present but untested.
- Secret redaction exists for persisted content and error messages, but
  the only fixture is a manual smoke input; no automated tests.
- No configuration-file discovery and no environment fallback: every run
  requires the full CLI surface (roadmap Phase 1 "configuration
  discovery" undelivered).
- `--json` exists but its payload shape is undocumented (no contract).

`scripts/check_documentation.py`:

- Validates raw events, detects spool, strict gate (AS-007) present but
  untested.
- No config/env fallback; JSON payload undocumented.
- Hand-rolled frontmatter parser is intentionally minimal (raw events
  use flat JSON-quoted scalars); retained.

### Plan

1. Add `scripts/atlas_config.py` (stdlib only): upward discovery of
   `atlas-agent.yaml` / `.atlas-agent.yaml`, a documented minimal
   YAML-subset parser (two-level maps, scalars), and a resolver with
   precedence CLI > environment (`ATLAS_*`) > config file > default.
2. Wire config/env fallback into both scripts (`--config`, optional
   identity/context arguments). Exit codes unchanged: 0 ok, 1 findings
   (check), 2 usage, 3 operational (capture).
3. Refactor `main()` to accept an argv list for in-process testing.
4. Add pytest suite under `atlas-vault-documentation/tests/` covering
   AS-002, AS-003, AS-004, AS-005 (expanded, never printing secret
   values), AS-006, AS-007, AS-008, AS-018, atomicity (no temp residue),
   config discovery/env precedence, and JSON output contracts.
5. Add `references/JSON-OUTPUT-CONTRACT.md` and extend
   `config/atlas-agent.example.yaml` with the new optional keys.
6. Run the full validation suite (subproject tests + parent repo gates).
7. Document the work through the skill itself: capture real events into
   a fresh Atlas vault with `capture_event.py`, validate with
   `check_documentation.py --strict`, and issue an ATLAS-DOC-RECEIPT.

### Results

**Status: complete — all required work delivered and validated.** (2026-08-01)

Exact commands and results:

```
$ cd atlas-vault-documentation && ../.venv/bin/python -m pytest tests -q
60 passed

$ .venv/bin/python -m pytest            (parent repo suite, unaffected)
54 passed

$ .venv/bin/python -m ruff check .      (parent gate)
All checks passed!  (exit 0)

$ .venv/bin/python -m mypy src          (parent gate)
Success: no issues found in 14 source files  (exit 0)

$ python3 -m py_compile atlas-vault-documentation/scripts/*.py
exit 0  (scripts remain dependency-free, stdlib-only)

$ python3 atlas-vault-documentation/scripts/capture_event.py --help
exit 0 on the system interpreter (no venv, no third-party imports)
```

Skill-self documentation (real events, captured with `capture_event.py`
into a fresh `atlas init` vault at `.tmp/atlas-vault`):

- `AE-20260801T130114Z-project-atlas-a888e339` — implementation event;
- `AE-20260801T130128Z-project-atlas-5de65cd9` — validation event;
- `AE-20260801T130141Z-project-atlas-322a7711` — completion event.

```
$ python3 atlas-vault-documentation/scripts/check_documentation.py \
    --vault .tmp/atlas-vault --strict --json
{"ok": true, "files_checked": 3, "pending_spool": 0, "errors": []}  (exit 0)
```

Acceptance coverage delivered by the new suite (60 tests):

- AS-002 `TestImmediateCapture` — one atomic date-partitioned write, no
  temp residue, correct capture-state frontmatter.
- AS-003 `TestStableEventId` — explicit ID stable in path, frontmatter,
  and across validation (byte-identical file after check).
- AS-004 `TestDuplicateEventId` — different payload under an existing ID
  exits 3, original bytes untouched; JSON error contract asserted.
- AS-005 `TestSecretRedaction` — fixture-driven (secret values loaded
  from `tests/fixtures/secret-event-input.txt`, never printed), six
  pattern classes, private-key blocks, error-message redaction.
- AS-006 `TestSpoolFallback` — spool write with `sync_state: pending`.
- AS-007 `TestStrictSpoolGate` — strict gate via CLI, config file, and
  `ATLAS_STRICT`; non-strict reports but passes; empty spool passes.
- AS-008 `TestControlledTaxonomy` / `TestValidatorTaxonomy` — CLI
  rejects unsupported kinds (exit 2); validator flags bad kinds, secret
  content, missing keys, self-asserted `verified`, malformed
  frontmatter; script taxonomy checked against `MDA-STANDARD.md`.
- AS-018 `TestPathSafety` — traversal event IDs rejected (exit 2, no
  writes), `ensure_descendant` escape tests, symlink-escape test.
- JSON contracts — `references/JSON-OUTPUT-CONTRACT.md` plus
  `TestJsonContract` on both scripts (success, failure, strict payloads).

### Remaining risks

- Normalization and routing are intentionally out of scope: captured
  events carry `normalization_state: pending` until mda-cli integration
  (roadmap Phase 3). Live mda-cli runs were not executed (no provider).
- The config parser supports a documented YAML subset only; files using
  lists or deeper nesting fail with a clear error rather than being
  misread. Full YAML would require a dependency the capture path must
  not take (FR-S003).
- `.tmp/atlas-vault` holds the evidence vault for this run and is
  git-ignored; recapture from this WORKLOG if it is cleaned.
- AS-017 (multi-agent uniqueness) relies on entropy in generated IDs;
  explicit-ID collisions are already fail-closed. A dedicated multi-agent
  test belongs with the agent-hooks phase (roadmap Phase 5).
- `capture_event.py` retains its original stdlib style (e.g.
  `datetime.timezone.utc`); the parent ruff config intentionally does not
  lint this subproject.

---

## AS-WP-002 — mda-cli Normalization Integration and Provenance Hardening

**Status:** complete
**Started:** 2026-08-01
**Scope:** `atlas-vault-documentation/` subproject, roadmap Phase 3.
Acceptance tests AS-009, AS-010, AS-011, AS-012, AS-019. Zero
regressions against AS-WP-001 (60 tests) and parent gates (54 tests).

### Plan

1. `internal/` subsystem (stdlib only), clearly separated:
   - `process_runner.py` — explicit-argv execution, timeout, redacted
     capture, failure classification (executable-missing,
     permission-denied, timeout, process-failed);
   - `provenance.py` — streaming SHA-256, provenance block construction
     and atomic frontmatter injection;
   - `verification.py` — untrusted-output verification: existence,
     single unambiguous candidate, inside-root, readability, frontmatter,
     raw-source reference, secret scan, unexpected-file detection;
   - `normalization.py` — orchestration: settings resolution, command
     building, retry policy, output discovery, failure records.
2. `scripts/normalize_event.py` — CLI composing the subsystem with the
   existing validators. Exit codes: 0 ok, 2 usage, 3 operational (unsafe
   path, ambiguous pre-existing output), 4 normalization failure, 5
   verification failure.
3. Command construction: argument arrays only, never shell strings;
   provider names regex-validated; all paths resolved and root-checked;
   `--in-place` never emitted; sibling and output-folder modes.
4. Provenance: injected `atlas_provenance` frontmatter block (raw event
   ID + SHA-256, command, version, arguments, output mode, provider,
   verification status, timestamps). Raw events stay immutable.
5. Failures become structured evidence: redacted JSON failure record
   `<raw-stem>.normalization-failed.json` next to the raw event.
6. Config extension (backwards compatible): `normalization.*` keys
   (enabled, command, skill_id, skill_dir, provider, timeout, retries,
   output_mode, output_directory, verify, fail_on_warning, keep_raw,
   record_command); env `ATLAS_MDA_COMMAND`, `ATLAS_PROVIDER`,
   `ATLAS_NORMALIZATION_TIMEOUT`, `ATLAS_OUTPUT_MODE`,
   `ATLAS_AGENT_CONFIG`; discovery also covers `.atlas/agent.yaml`;
   `ATLAS_AGENT_ID` accepted as alias per references/AGENT-INTEGRATION.md.
7. Tests: mock `mda` executable (tests/fixtures/bin/mda) with scripted
   success/failure modes; success (sibling/directory), every failure
   category, security (traversal, symlink, provider injection, unicode,
   long paths), config precedence, dry-run, backwards compatibility.
8. Docs: `docs/NORMALIZATION.md` (architecture, workflow, failure
   taxonomy, troubleshooting), `references/PROVENANCE.md`, JSON contract
   update, config example update, VALIDATION_REPORT.md, this worklog.
9. Close the loop: capture real events, validate strict, receipt.

### Design decisions (recorded for auditors)

- The orchestrator records but does not forward `--provider` to mda-cli:
  provider selection is mda-cli's own configuration concern; the
  provenance block records the configured provider name for audit.
- `--output-folder` is the directory-mode flag per SKILL.md ("sibling or
  explicit output-folder mode"); sibling mode writes
  `<raw-stem>.normalized.md` next to the raw event.
- A pre-existing expected output aborts before mda-cli runs (exit 3):
  normalization never overwrites.
- `keep_raw` is accepted for forward compatibility but is not optional
  behaviorally: raw evidence is always immutable (FR-S005).

### Results

**Status: complete — normalization integration delivered, zero regressions.** (2026-08-01)

Exact commands and results:

```
$ cd atlas-vault-documentation && ../.venv/bin/python -m pytest tests
112 passed in 8.29s        (60 from AS-WP-001 + 52 added in AS-WP-002)

$ .venv/bin/python -m pytest          (parent repo suite)
54 passed

$ .venv/bin/python -m ruff check .    All checks passed!  (exit 0)
$ .venv/bin/python -m mypy src        no issues in 14 source files  (exit 0)
$ python3 -m py_compile scripts/*.py internal/*.py   exit 0 (stdlib-only)
```

End-to-end pipeline on the real evidence vault (`.tmp/atlas-vault`),
using the deterministic mock for mda-cli:

```
$ normalize_event.py --event <6 raw events> --mda-command tests/fixtures/bin/mda
6x {"ok": true, "status": "normalized", "verification_status": "verified"}

$ check_documentation.py --vault .tmp/atlas-vault --strict --json
{"ok": true, "files_checked": 12, "raw_checked": 6,
 "normalized_checked": 6, "pending_spool": 0, "errors": []}   (exit 0)
```

Integration finding fixed during validation: `check_documentation.py`
applied raw-event rules to `*.normalized.md` files. Raw and normalized
events are now validated with distinct rule sets
(`validate_normalized_event`: type, source reference, atlas_provenance
block with raw_event_id/raw_event_hash/verification_status, secret
scan). JSON payload gained `raw_checked` / `normalized_checked`
(additive, backwards compatible); 4 new tests cover it.

Acceptance matrix:

```
AS-009  PASS  --in-place never constructed; raw SHA-256 unchanged
AS-010  PASS  atlas_provenance block + source:agent-event reference
AS-011  PASS  verification independent of mda exit code; exit-0-with-
              no-output and all malformed-output modes fail
AS-012  PASS  command text and exact counts preserved by contract;
              verification enforces frontmatter/identity/source refs
AS-019  PASS  executable-missing, permission-denied, timeout (+retry
              attempts), provider failure: raw intact, structured
              failure record, normalization stays pending
```

AS-WP-002 events captured through the skill itself:

- `AE-20260801T133445Z-project-atlas-014668a6` — implementation
- `AE-20260801T133503Z-project-atlas-a3425c9c` — validation
- `AE-20260801T133516Z-project-atlas-a6867d5d` — completion
  (normalized: `AE-...a6867d5d.normalized.md`, verified)

All six raw events in the evidence vault have verified normalized
counterparts with `atlas_provenance` blocks.

Engineering metrics:

- Files added: 12 (5 internal/scripts modules, 2 test modules, 1 mock,
  2 docs pages, 1 provenance spec, 1 worklog section) + this report
- Files modified: 9 (atlas_config, capture_event, check_documentation,
  conftest, test_check_documentation, JSON contract, config example,
  README, VALIDATION_REPORT)
- Tests added: 52 (48 normalization/internal + 4 normalized-validation);
  total 112
- New module lines: ~1,620 (incl. tests + mock); docs pages: 3 new
  (~180 lines) + 2 updated
- Validation runtime: ~8.3s subproject suite; ~4s parent suite;
  normalization runtime ~0.2s per event (mock, no provider)

### Remaining risks

- Live mda-cli with a real provider was not exercised (offline
  environment); the mock pins the command surface (`--skill-dir`,
  `--output-folder`, `--version`, positional input). First live run
  should compare mda-cli's actual output naming against
  `expected_output()` and adjust the discovery convention if needed.
- A verification-failed artifact is intentionally left in place for
  inspection; rerunning then fails closed with `output-exists` until a
  human quarantines it (documented in docs/NORMALIZATION.md).
- check_documentation now validates normalized events with a basic
  rule set; full normalized-frontmatter schema validation (MDA-STANDARD
  section 3 field-by-field) is deferred to the validation hardening
  phase alongside the Atlas router (Phase 4).
- `--provider` is recorded in provenance but deliberately not forwarded
  to mda-cli (provider selection is mda-cli's own configuration); if a
  future mda-cli version exposes a provider flag, a pass-through option
  can be added without breaking the contract.
- `.tmp/atlas-vault` evidence vault is git-ignored; event IDs and hashes
  are recorded in this worklog.

---

## AS-WP-003 — Atlas Router, Canonical Placement and Safe Projection

**Status:** complete
**Started:** 2026-08-01
**Scope:** `atlas-vault-documentation/` subproject, roadmap Phase 4.
Acceptance tests AS-013, AS-014, AS-015, AS-016, AS-017, AS-020.
Zero regressions against 119 subproject + 54 parent tests.

### Key design decisions (recorded for auditors)

- **Projections are deterministic pure functions of routing state +
  event evidence.** Project log, work-package pages, and the project
  index are regenerated wholesale inside `ATLAS:BEGIN/END` generated
  regions. Idempotency is therefore structural: replay renders
  byte-identical content and no write occurs. No free-form text
  matching is used anywhere; routing state JSON is the replay authority.
- **Optimistic per-project transactions:** lock file
  (`routing/state/<project>.lock`, O_EXCL, stale after
  `stale_lock_seconds`, bounded wait), expected pre-write SHA-256
  preconditions, full staging in memory, journal-based rollback
  (original bytes restored on promote failure), receipt written only
  after successful promotion.
- **Deterministic identifiers:** receipt IDs and transaction IDs derive
  from SHA-256 of the event ID + normalized hash / plan hash, so replay
  returns the original receipt and no wall-clock randomness enters
  identity. Wall-clock appears only in `routed_at` audit fields.
- **Event placement is `reference` by default:** project event pages
  are generated reference pages carrying metadata, hashes, and links to
  the immutable raw/normalized artifacts — no uncontrolled content
  duplication.
- **Schemas are contract documents:** JSON schema files ship under
  `schemas/` and are enforced in tests via jsonschema (dev dependency);
  runtime stays stdlib-only with structural checks.
- Root confinement, redaction, and path validation reuse the AS-WP-001
  and AS-WP-002 hardened helpers.

### Results

Certified on 2026-08-01. Full evidence, exact commands, test counts, mypy
typing result, transaction/concurrency probes, and the acceptance matrix are
recorded in `atlas-vault-documentation/AS-WP-003-CERTIFICATION.md`.

### Remaining risks

Live provider normalization remains outside AS-WP-003; routing certification
uses verified offline fixtures and the deterministic local test harness.

---

## AS-WP-004 — Project Discovery, Documentation Inventory and Governed Ingestion

**Status:** certified
**Started:** 2026-08-01
**Scope:** bounded Stage 1 Project Atlas golden fixture.

Implemented deterministic discovery, inventory, classification, authority,
incremental state, capture/normalize/verify/route orchestration, documentation
map, coverage, conflict, Graphify deferral, receipts, strict validation,
rollback, controlled Stage 2 fixtures, incremental mutations, and the
performance baseline. Final evidence is recorded in
`atlas-vault-documentation/AS-WP-004-CERTIFICATION.md`.

---

## AS-WP-005 — Graphify Adapter, Relationship Validation and Derived Knowledge Projections

**Status:** certified
**Completed:** 2026-08-01

Implemented inventory-backed Graphify schema acceptance, deterministic JSON/JSONL
parsing, canonical nodes and relationships, project-local identity resolution,
source-document verification states, duplicate collapse, conflict/orphan
quarantine, incremental graph state, router-owned derived projections, strict
validation, receipts, focused fixtures, and graph performance benchmarks.
Final evidence is recorded in
`atlas-vault-documentation/AS-WP-005-CERTIFICATION.md`.

---

## AS-CTRL-001 — Universal Agent Bootstrap and Atlas Documentation Enforcement

**Status:** certified
**Started:** 2026-08-01

Implemented canonical skill hashing, generated adapters, logical Vault identity,
managed bootstrap, session state, unified event commands, spool-aware preflight,
receipt gating, capability registry and control-plane tests. Independent
recertification reproduced the original shared-directory race, verified the
capture-through-route per-Vault lock, passed 10 consecutive concurrency runs,
and passed the complete 146-test control-plane suite. See
`atlas-vault-documentation/AS-CTRL-001-CERTIFICATION.md`.
## AS-SKILL-001 — Atlas Governed Work Lifecycle Skill

Certified. Added the canonical operational skill package, minimal generated
bootstrap shims, skill acknowledgement, capability check, real event pipeline
integration, readiness registry, and lifecycle evidence. See
`atlas-vault-documentation/AS-SKILL-001-CERTIFICATION.md`.

## AS-CORE-002 — Semantic Domain Model and Source Lifecycle Hardening

**Status:** certified
**Merged:** 2026-08-02
**Merge commit:** `50509a2`
**Evidence:** `docs/AS-CORE-002-post-merge.md` and
`docs/evidence/AS-CORE-002-post-merge-receipt.yaml`

The semantic implementation, strict nested schemas, lifecycle-state
validation, secret exclusion, human-safe regeneration and two-phase ingestion
write plan are merged into `main`. The full repository suite passed **88
tests**; the earlier receipt's 87 was corrected as an undercount. Agent Two's
independent replay confirmed zero mutations for the cross-project malformed
marker failure and recommended merge.

Deferred items remain richer Claim and Concept population,
schema/Pydantic coercion edge cases, generated-marker convention
reconciliation, state-migration tooling, and real-project pilot
certification.

## AS-CORE-002 source-lifecycle erratum

**Status:** recertified — merge eligible, evidence amendment recorded
**Hotfix branch:** `fix/source-lifecycle-replay`
**Evidence:** `docs/AS-CORE-002-source-lifecycle-erratum.md` and
`docs/evidence/AS-CORE-002-source-lifecycle-recertification.yaml`

Independent review reproduced a P0 defect where source-change observations
were written into the semantic `DocumentLifecycle` field. The hotfix separates
document lifecycle from source-change state, repairs only known legacy values,
rejects unknown corruption, and adds deletion/no-op, restore, rename,
migration, strict-validation and rollback coverage. Agent Two verification is
required before recertification.

Implementation commit: `2cb0d8b`. Local evidence is complete; the hotfix is
independently recertified by Agent Two as merge eligible. This evidence-only
amendment corrects the repository-suite labeling and stale remediation status;
the implementation commit remains frozen.

## AS-ID-001 — Durable Source Lineage Identity

**Status:** implementation complete — governor review required
**Base:** `313712ee28083693ae39470b2d7148dc74617322`
**Architecture:** `ae98fba`
**Implementation:** `058a954`
**Evidence:** `docs/evidence/AS-ID-001-receipt.yaml`

Added UUIDv4 project genesis, Core-local single-winner synchronization, source
registry v2, durable lineage derivation, canonical paths, raw-byte fingerprints,
v1 migration receipts, duplicate-project detection, strict lineage validation,
and lifecycle replay/rollback fixtures. The full Core and Control Plane suites,
static checks, compilation, and public workflow tests pass. AS-CORE-003 remains
frozen pending this package's independent review.

## AS-ID-001 governor remediation

**Status:** implementation complete — independent review required
**Blocked candidate:** `907363a`
**Implementation:** `455dace`
**Evidence:** `docs/evidence/AS-ID-001-governor-remediation-receipt.yaml`

Remediated bounded architecture findings for continuity-chain migration,
evidence-scoped candidate uniqueness, deterministic unresolved findings, formal
registry schema validity, post-promotion verification, and real public
multi-process genesis. The Core suite is now 112 passed versus 103 on the
blocked candidate; the Control Plane remains zero-diff and 146 passed. The
referenced governor report file was unavailable in this checkout; its absence
and the directive-based defect register are disclosed in the receipt.

## AS-CORE-003 durable-lineage integration merge

**Status:** merged to `main` — governance approved
**Merge commit:** `a3fdb711dd0b3b1b00b8984482dcb4c1d63e3998`

The AS-CORE-003 durable-lineage integration was merged with governance
authorization. Post-merge validation passed: Core `135 passed`, mypy clean for
32 source files, Ruff clean, and compilation clean. The Control Plane remained
unchanged.

## AS-CORE-003 restored-claim replay remediation

**Status:** remediation complete — independent recertification required
**Base:** `21e533aa691b1d538fcd818f678a4ac27ef62254`
**Implementation:** `3d8412f`

Fixed the governed lifecycle replay edge so an equivalent observation after
`RESTORED` transitions to `UNCHANGED` instead of attempting the invalid
`RESTORED -> RESTORED` transition. Regression coverage verifies restored replay
stability and restored rename claim identity. Core remains `135 passed`; mypy,
Ruff, and compilation remain clean. AS-CORE-003 certification is reopened
pending Agent Two recertification and Agent Three architecture re-approval.

## AS-CORE-003 architecture re-approval

**Status:** implementation complete — architecture re-approved
**Implementation:** `3d8412f764652ed67126ab09fd56521209cf9edf`
**Evidence:** `073a4744f2a05c49a882b3881b14a74a454d446a`

Agent Three re-approved the bounded restored-claim replay remediation. The
transition table and promotion boundary remain unchanged; equivalent replay
now transitions `RESTORED -> UNCHANGED`. Final release/merge control remains
with the project owner.

## AS-SPEC-004 OKF v0.2 conformance

**Status:** implementation complete — governor review required
**Base:** `098c5e7ea030d4c52e742e71f45ac10639c66513`

Added deterministic OKF v0.2 YAML frontmatter for generated concept notes,
validated Atlas extensions and resources, generic handling for unknown concept
types, golden-file coverage, protected-region preservation, and unchanged
replay checks. Core passed `140` tests (135 baseline plus 5 new tests), the
Control Plane passed `146`, mypy passed for `33` source files, Ruff passed, and
compilation passed. Architecture governor review remains pending.

## AS-SPEC-004 public concept-type wiring remediation

**Status:** remediation complete — independent certification required
**Previous implementation:** `9dd7ce5668658d4bae0e33d0c0fee9d0d765a6ab`
**Remediation implementation:** `1297b1525413e39b16567610eade60bc28fa21a9`

Wired the optional top-level `concept_type` from the authoritative project
marker through public ingestion into the existing generic fallback. Public
workflow coverage now proves unknown types render as `Reference`, absent types
retain `Project`, and known types such as `Architecture` are preserved. Core
passed `142` tests; Control Plane passed `146`; mypy, Ruff, and compilation
remained clean. AS-SPEC-004 certification and governance rereview are reopened.

## AS-SPEC-004 architecture re-approval

**Status:** implementation complete — architecture re-approved
**Implementation:** `1297b1525413e39b16567610eade60bc28fa21a9`
**Evidence:** `2f5c718c84e96871d1e3b9ef91f0840df52f2975`

Agent Three re-approved the public `concept_type` wiring remediation. The
marker remains the authoritative project-level concept-type source, unknown
values continue through the existing generic `Reference` fallback, and the
single promotion boundary and certified identity/lifecycle paths remain
unchanged. Final merge control remains with the project owner.

## AS-ENG-005 ingestion and retrieval foundation

**Status:** implementation complete — independent certification required
**Base:** `d2231d0e8659b9559c0e70bd9f9e58e80042f56b`
**Implementation:** `d084491`

Added deterministic canonical indexes for sources, claims, concepts, conflicts,
authority, and provenance; a read-only exact/prefix retrieval API; atomic index
staging through the existing ingestion promotion boundary; index-integrity
validation; and idempotent initialization for existing Atlas scaffolds. The
isolated public workflow passed, stabilized replay was byte-identical, Core
passed `145`, Control Plane passed `146`, mypy passed for `34` source files,
Ruff passed, and compilation passed. No certified subsystem semantics or
Control Plane files changed.

## AS-RET-001 lexical retrieval index reclassification and remediation

**Status:** remediation complete — governor rereview required
**Base:** `d2231d0e8659b9559c0e70bd9f9e58e80042f56b`
**Historical implementation:** `d084491b28b5dd43e3e59900c5dab716466d4c7f`
**Historical corrected evidence:** `0da869a49729c61c7a24a1127d5c3de545f5eb95`
**Remediation implementation:** `4a40b3816bb24edd0d07271f6dd9c39dc1608a57`

Reclassified the prior lexical exact/prefix index and retrieval work from the
undocumented AS-ENG-005 label to governed AS-RET-001. The historical commit
title said “semantic retrieval foundation”; its implementation contains no
semantic, vector, embedding, ANN, or similarity capability.

Moved all retrieval and navigation projections from `vault/indexes/` to
`vault/generated/indexes/` and `vault/generated/navigation/`. Canonical state
remains under `state/`; generated indexes are disposable and rebuilt from
canonical state. An obsolete `vault/indexes/` directory now fails closed with
a regeneration instruction. Retrieval remains read-only and the existing
single promotion boundary is unchanged.

The worktree serialization audit found no active in-flight owner of
`src/project_atlas/ingestion.py`; overlapping committed deltas belonged only
to frozen historical review or architecture worktrees. Core passed `149`,
Control Plane `146`, mypy was clean for `34` source files, Ruff passed, and
compilation passed.

## VERIFY branch supersession closure for AS-RET-001 sequencing

**Status:** owner decision recorded — verify branch formally superseded
**Decision record:** `docs/architecture-governance/VERIFY-AS-RET-SEQUENCING-DECISION.md`
**Main base:** `d2231d0e8659b9559c0e70bd9f9e58e80042f56b`
**Verify head:** `04a62feb5de32c4f917ca405f2d46bfe8f56d1e4`
**Superseding merge:** `a3fdb711dd0b3b1b00b8984482dcb4c1d63e3998`
**AS-RET candidate:** implementation `4a40b3816bb24edd0d07271f6dd9c39dc1608a57`,
evidence `f1925abe521c3439b7bf5159f504c992ce47246b`

`verify/atlas-core-vertical-slice` is formally closed as superseded. The branch
contains an earlier incomplete AS-CORE-003 implementation and was superseded by
the later governance-approved AS-CORE-003 integration merged at
`a3fdb711dd0b3b1b00b8984482dcb4c1d63e3998`.

Historical commits and evidence remain immutable. The verify branch is not an
active work package, does not own `src/project_atlas/ingestion.py`, and must
not be merged or cherry-picked into AS-RET-001.

## VERIFY/AS-RET sequencing decision consistency correction

Corrected the governance decision record for sequencing consistency: verify
supersession remains the disposition, `selected_option` is now `1`, and options
`2` and `3` are explicitly rejected in
`docs/architecture-governance/VERIFY-AS-RET-SEQUENCING-DECISION.md`. Updated
`docs/evidence/AS-RET-001-receipt.yaml` serialization review to reference the
corrected owner-decision option and commit (`decision_commit: SELF`).

## AS-RET-001 architecture re-approval

**Status:** implementation complete — architecture re-approved
**Implementation:** `4a40b3816bb24edd0d07271f6dd9c39dc1608a57`
**Evidence:** `f1925abe521c3439b7bf5159f504c992ce47246b`

Architecture Governor performed a targeted rereview following the
verify/AS-RET sequencing decision consistency correction
(`ca2aa9c5afb66bcfbb532848084fc42fb3b4181d`) and re-approved the AS-RET-001
lexical retrieval index candidate. Independent findings:

- The remediation implementation commit (`4a40b381...`) makes no changes to
  `src/project_atlas/ingestion.py`. The only ingestion.py delta present on
  the branch relative to the certified base integrates derived index writes
  into the existing staged `write_plan` ahead of the single `_promote(
  write_plan)` call — the single promotion boundary is preserved, and there
  is no direct/out-of-band compiler write.
- A patch-id comparison against `verify/atlas-core-vertical-slice` found no
  shared commits; the branch does not incorporate or depend on verify work,
  confirming the decision record's non-contamination claim.
- The corrected decision record and `docs/evidence/AS-RET-001-receipt.yaml`
  now agree: `selected_option: 1`, options 2 and 3 explicitly rejected,
  `decision_commit: SELF` resolves to the correction commit.
- Control Plane diff against the certified base remains zero.

Independent re-run (not taken from the receipt): Core `149 passed`, Control
Plane `146 passed`, mypy clean for `34` source files, Ruff clean. Counts match
the receipt exactly. Final merge control remains with the project owner.
