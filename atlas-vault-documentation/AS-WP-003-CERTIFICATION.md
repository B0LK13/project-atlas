# AS-WP-003 Certification

**Disposition:** AS-WP-003 CERTIFIED — all router, regression, lint, compilation,
typing, transaction, concurrency, and strict validation gates pass.

**Date:** 2026-08-01

## Executive summary

The Atlas router is certified against the local repository gates. Routing state
is the replay authority; project pages are deterministic projections; promotion
is protected by a per-project lock, expected pre-write hashes, staging, and
rollback behavior. No approved type baseline remains because the exact
repository-wide mypy command is green.

## Commands and metrics

| Gate | Exact command | Result |
|---|---|---|
| Router-focused tests | `cd atlas-vault-documentation && ../.venv/bin/python -m pytest tests/test_router.py -q` | 7 passed |
| Full subproject tests | `cd atlas-vault-documentation && ../.venv/bin/python -m pytest tests -q` | 119 passed |
| Parent repository tests | `.venv/bin/python -m pytest -q` | 54 passed |
| Ruff | `.venv/bin/python -m ruff check .` | passed |
| Compilation | `.venv/bin/python -m py_compile atlas-vault-documentation/internal/*.py atlas-vault-documentation/scripts/*.py` | passed |
| Router/repository typing | `.venv/bin/python -m mypy src atlas-vault-documentation` | passed; 46 source files |
| Mypy version | `.venv/bin/python -m mypy --version` | mypy 2.3.0 |
| CLI smoke | `route_event.py --help`, `rebuild_project.py --help`, `validate_routes.py --vault .tmp/atlas-vault --json` | passed; 0 projects in empty scaffold |

Mypy used `/mnt/d/project-atlas-vault/pyproject.toml`. The historical AS-WP-002
record ran `.venv/bin/python -m mypy src` successfully; the broader command was
not recorded at that point. The current broader command is green, so there are
zero current findings and no deferred type-debt baseline.

The earlier `56 passed` statement was a scoped/interrupted-run figure and is
not the full subproject count. Current authoritative counts are 7 router,
119 subproject, and 54 parent tests.

## Recovery and architecture evidence

- `RoutedEventRecord.status` is persisted with a backward-compatible
  `unknown` default, enabling validation-event projection.
- Project log duplicate validation counts only the canonical event-page link,
  not raw-evidence filenames containing the same event ID.
- Replay checks event ID plus normalized SHA-256 and returns the original
  receipt without mutation.
- Route receipts are promoted only with the staged transaction and include
  plan, transaction, source hashes, updates, and synchronized state.
- Local typing fixes were limited to explicit callable/path/dictionary
  annotations and safe narrowing; behavior was covered by the existing suite.

## End-to-end and failure evidence

`tests/test_router.py` verifies a fresh disposable vault with implementation,
validation, and completion events. It proves canonical event placement,
routing-state persistence, newest-first project-log ordering, validation
status, completed work-package projection, index/log/event links, receipts,
and strict `validate_project` success.

The same test suite proves replay byte identity and conflicting duplicate
rejection. The transaction test injects failure before promotion, verifies no
project pages, state, or success receipt are created, verifies a structured
failure record, and confirms retry succeeds after restoring promotion.

Generated-region tests prove outside text preservation, byte-identical no-op
updates, mismatched-marker rejection, and duplicate-region rejection.

Concurrency tests use two worker threads and the real per-project lock:

- different events: both commit once;
- same identical event: one `routed`, one `idempotent-replay`;
- same ID with conflicting content: one idempotent replay and one structured
  `duplicate-conflict` failure;
- validation succeeds with exactly three retained events and no duplicate log
  entries.

## Acceptance matrix

| Requirement | Result | Evidence |
|---|---|---|
| AS-013 canonical event placement | PASS | fresh-vault sequence test |
| AS-014 idempotent project-log projection | PASS | replay and strict validation tests |
| AS-015 work-package and project-state updates | PASS | validation/completion sequence test |
| AS-016 human-safe generated regions | PASS | generated-region preservation/fail-closed test |
| AS-017 multi-agent uniqueness and concurrency | PASS | two-worker different-event and replay test; transaction failure test |
| AS-020 strict routing validation and receipts | PASS | `validate_project` and receipt assertions |

## Compatibility, residual risk, and next gate

The parent package suite remains unchanged and passes. Existing raw and
normalized evidence is immutable; the router writes only under the configured
vault root. Live provider normalization remains outside this work package and
was not required for the offline router certification.

AS-WP-004 — Project Discovery, Inventory and Documentation Ingestion may begin.
Its writes must continue to use the router as the approved write path.
