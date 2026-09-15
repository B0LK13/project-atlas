# AS-WP-004 Completion Report

**Disposition:** AS-WP-004 IMPLEMENTATION COMPLETE — CERTIFICATION PENDING.

**Date:** 2026-08-01

## Executive summary

AS-WP-004 now provides bounded project discovery, deterministic document
inventory, classification, authority assignment, incremental state, governed
capture/normalize/verify/route processing, documentation-map projection,
coverage, conservative conflict detection, Graphify deferral, receipts, and
strict validation.

The Project Atlas golden fixture proves the complete Stage 1 workflow. Overall
certification remains pending until the controlled Stage 2 fixture set and a
recorded performance probe are completed.

## Engineering metrics and commands

| Gate | Command | Result |
|---|---|---|
| AS-WP-004 tests | `cd atlas-vault-documentation && ../.venv/bin/python -m pytest tests/test_ingestion.py -q` | 6 passed |
| Full subproject suite | `cd atlas-vault-documentation && ../.venv/bin/python -m pytest tests -q` | 125 passed |
| Parent suite | `.venv/bin/python -m pytest -q` | 54 passed |
| Typing | `.venv/bin/python -m mypy src atlas-vault-documentation` | 64 source files, no issues |
| Ruff | `.venv/bin/python -m ruff check .` | passed |
| Compilation | `.venv/bin/python -m py_compile atlas-vault-documentation/internal/*.py atlas-vault-documentation/scripts/*.py` | passed |

The router-focused AS-WP-003 suite remains 7 passed. The previous `56 passed`
figure is not the full subproject count; current authoritative counts are 7
router-focused, 125 subproject, and 54 parent tests.

## Architecture and authoritative artifacts

The subsystem uses four machine-authoritative artifact families:

- `ingestion/inventory/<project>.json` — deterministic source inventory and
  inventory hash;
- `ingestion/state/<project>.json` — revision and lifecycle state;
- `ingestion/plans/<project>-<hash>.json` — deterministic operations and plan
  hash;
- `ingestion/receipts/<project>-<hash>.json` — immutable ingestion receipt.

Human-facing `projects/<project>/documentation-map.md` is a router-owned
projection and is never written directly by the ingestion orchestrator.

Explicit roots are authoritative. Workspace scans are depth-bounded, do not
follow directory symlinks, skip conservative build/cache/VCS directories, and
require a project marker. `.atlas-project.yaml` supplies canonical identity,
aliases, authority paths, and discovery metadata. Unsafe or invalid roots fail
closed.

Inventory uses streamed SHA-256, case-folded normalized path ordering, and a
semantic hash that excludes volatile modification timestamps. Sensitive names
are metadata-only; unsupported formats remain visible as inventory-only
records. Classification records type, confidence, evidence, competing types,
and rule version. Primary, maintained, derived, and external authority is
explicit; Graphify output is derived and semantic ingestion is deferred.

## Pipeline, projections, and incremental behavior

Eligible records are captured with AS-WP-001, normalized and verified through
AS-WP-002 scripts, and routed through AS-WP-003. The ingestion layer never
calls mda directly and never writes project Atlas pages directly. Stable
document/hash-derived event IDs prevent duplicate unchanged records.

The documentation map groups records by function and includes classification,
authority, state, hash, warnings, coverage categories, and unresolved
conflicts. Coverage is categorical and evidence-backed. Status conflicts are
retained with source document IDs and no automatic resolution. Changed
documents create a new revision event; deleted documents remain in ingestion
state as `deleted` with their last-known hash.

## Golden-fixture evidence

The Project Atlas fixture contains 8 inventory records. The public CLI run
produced 5 eligible captures, 5 normalized artifacts, 5 verified artifacts,
and 5 routed events. One credential-named file was sensitive metadata-only;
one PDF was unsupported inventory-only; one Graphify file was derived,
inventory-only, and semantic-ingestion deferred. Strict ingestion validation
passed. The fixture
also surfaced one explicit status conflict without resolving it automatically.

The tests prove deterministic inventory, new/changed/unchanged/deleted diff
states, no-op replay with zero byte mutations, targeted changed-source
processing, deleted-source retention, strict rollback after injected
normalization failure, external-symlink quarantine, root-boundary rejection,
source links, documentation-map generation, and offline capture/normalize/
verify/route integration.

## Acceptance matrix — Stage 1

| Requirement | Result | Evidence |
|---|---|---|
| AS-021 deterministic project discovery | PASS | discovery/inventory test |
| AS-022 complete document inventory | PASS | inventory fixture and schema |
| AS-023 classification and authority | PASS | classification/authority assertions |
| AS-024 governed pipeline integration | PASS | golden CLI and orchestrator tests |
| AS-025 documentation-map projection | PASS | golden ingestion test; router projection |
| AS-026 documentation coverage | PASS | coverage artifact and map assertions |
| AS-027 incremental and no-op processing | PASS | no-op and changed-source tests |
| AS-028 stale/deleted/conflicting handling | PASS | deletion retention and conflict tests |
| AS-029 Graphify derived inventory | PASS | classification and deferral assertions |
| AS-030 strict validation and receipts | PASS | strict validate-ingestion CLI |

## Residual risks and certification blockers

- Stage 2 controlled fixtures are not yet implemented: documentation-rich,
  sparse, monorepo, and mixed-format projects need independent evidence.
- Performance bounds for a larger corpus have not been measured.
- YAML manifest handling currently uses the available PyYAML runtime and needs
  an explicit dependency/packaging decision if the subproject must remain
  stdlib-only.
- Broad semantic conflict analysis, binary conversion, Graphify relationships,
  and estate-wide monitoring remain deferred by scope.

Existing AS-WP-001 through AS-WP-003 tests remain passing. Source repositories
are not mutated, normalized output is not written in place, and Graphify
semantic ingestion remains disabled.
