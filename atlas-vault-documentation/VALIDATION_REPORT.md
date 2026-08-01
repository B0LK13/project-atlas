# Validation Report

## AS-WP-002 automated suite (2026-08-01)

- pytest suite `tests/`: 108 passed, 0 failed (60 from AS-WP-001, 48 added).
- AS-009 raw immutability: `--in-place` is never constructed; raw hash
  unchanged after normalization (`test_sibling_mode_end_to_end`).
- AS-010 normalized provenance: `atlas_provenance` block with raw event
  ID, SHA-256, command, version, provider, output mode, verification
  status (`TestSuccessfulNormalization`).
- AS-011 conservative status: verification is independent of the mda-cli
  exit code; `missing-output` and all malformed-output modes fail
  (`TestFailureHandling`).
- AS-012 exact validation retention: the mock preserves command text and
  pass counts; verification enforces frontmatter, identity, and source
  references (`test_verification_failures`).
- AS-019 provider degradation: executable-missing, permission-denied,
  timeout (with bounded retries), and provider failure all leave raw
  evidence intact with `normalization_state: pending` and a structured
  failure record (`TestFailureHandling`).
- Security: provider-name injection, symlink escape, output outside
  root, unicode, long paths, no-shell command construction
  (`TestSecurity`, `test_no_shell_invocation`).
- Backwards compatibility: all AS-WP-001 tests pass unchanged;
  capture/check exit codes and CLI surface untouched.
- Live mda-cli runs remain unexecuted (no provider installed); a
  deterministic mock (`tests/fixtures/bin/mda`) scripts every success
  and failure category offline.

## AS-WP-001 automated suite (2026-08-01)

- pytest suite `tests/`: 60 passed, 0 failed.
- AS-002 immediate atomic capture: covered (`TestImmediateCapture`).
- AS-003 stable event ID: covered (`TestStableEventId`).
- AS-004 duplicate IDs fail closed, original preserved: covered
  (`TestDuplicateEventId`).
- AS-005 secret redaction, expanded patterns, fixture-driven, no secret
  values printed: covered (`TestSecretRedaction`).
- AS-006 spool fallback with `sync_state: pending`: covered
  (`TestSpoolFallback`).
- AS-007 strict spool gate (CLI, config, and env paths): covered
  (`TestStrictSpoolGate`).
- AS-008 controlled taxonomy (CLI and validator sides, taxonomy matches
  `MDA-STANDARD.md`): covered (`TestControlledTaxonomy`,
  `TestValidatorTaxonomy`).
- AS-018 path safety (traversal IDs, root escape, symlink escape):
  covered (`TestPathSafety`).
- Configuration discovery and environment fallback: covered
  (`test_atlas_config.py`, `TestConfigAndEnvFallback`).
- JSON output contracts: documented in
  `references/JSON-OUTPUT-CONTRACT.md`, covered (`TestJsonContract`).

## Package validation

- Python helper compilation: passed
- Immediate raw capture: passed
- Secret redaction smoke test: passed
- Raw-event validation: passed
- Duplicate event ID rejection: passed
- Duplicate attempt exit code: `3`
- Original event unchanged after duplicate attempt: passed
- Spool fallback capture: passed
- Strict unsynchronized-spool gate: passed
- Strict spool check exit code: `1`

## Scope

These are deterministic local smoke tests. Live mda-cli provider normalization was not executed because it depends on an installed mda-cli environment and configured provider credentials.

## Next validation work

- live mda-cli normalization fixture against a real provider;
- normalized-event JSON-schema validation;
- idempotent Atlas router tests;
- protected-region routing tests;
- full receipt gate.

## AS-WP-003 certification

See [AS-WP-003-CERTIFICATION.md](AS-WP-003-CERTIFICATION.md). The certified
gates are 7 router-focused tests, 119 full subproject tests, 54 parent tests,
Ruff, compilation, repository-wide mypy, fresh-vault routing, replay/conflict
handling, transaction failure injection, generated-region safety, concurrency,
and strict route validation.

## AS-WP-004 completion

See [AS-WP-004-COMPLETION-REPORT.md](AS-WP-004-COMPLETION-REPORT.md). Stage 1
Project Atlas golden-fixture implementation is complete and validated. Overall
AS-WP-004 certification is pending the controlled Stage 2 fixture set and a
recorded performance probe.
