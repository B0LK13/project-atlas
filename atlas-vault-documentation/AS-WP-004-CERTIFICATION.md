# AS-WP-004 Certification — Controlled Fixtures, Performance Baseline and Final Promotion

## 1. Executive summary

AS-WP-004 CERTIFIED — controlled Stage 2 fixtures, deterministic incremental behavior, strict validation, regression, typing, security and performance-baseline gates pass.

The certified path is bounded discovery → deterministic inventory → classification and authority assessment → capture → normalize/verify → router-only projection → coverage/conflict validation → immutable receipt. Graphify artifacts are inventoried as derived data and remain semantically deferred.

## 2. Final certification status

Status: certified. Stage 1 and Stage 2 correctness gates passed; the provisional local performance budgets passed for discovery/inventory, no-op replay and single-file incremental inventory. Full first-ingestion throughput is reported rather than treated as a hard SLA.

## 3. Scope and non-goals

Included controlled fixtures, bounded discovery, inventory, classification, authority, incremental state, rename history, safe sensitive/unsupported handling, documentation-map and coverage projections, rollback/retry, receipts, and validation. Graph database deployment, semantic Graphify relationships, autonomous conflict resolution, and estate-wide monitoring remain AS-WP-005+ scope.

## 4. Engineering metrics and files

Stage 2 added five synthetic fixture projects, four focused certification tests, the deterministic benchmark script `scripts/benchmark_ingestion.py`, rename/path-history state handling, Graphify classification for non-text outputs, and this evidence package. The full subproject suite is 129 tests; the parent suite is 54 tests.

## 5. Stage 1 regression

Project Atlas golden regression remained coherent: 8 documents discovered, 5 routed, 1 sensitive, 1 unsupported PDF, and 1 deferred Graphify artifact. The inventory reports two unsupported-state records when the deferred Graphify artifact is included; the receipt reports Graphify separately. Strict validation passed.

## 6. Stage 2 fixture definitions and results

| Fixture | Result | Evidence |
|---|---|---|
| documentation-rich | PASS | `test_stage2_workspace_discovery_and_monorepo_policy_are_deterministic`, `test_rich_sparse_mixed_and_graphify_fixtures_ingest_safely` |
| sparse-readme | PASS | sparse coverage remains missing; no claims are fabricated |
| monorepo | PASS | root is canonical by default; explicit separate policy discovers web/api/shared |
| mixed-formats | PASS | 3 sensitive metadata-only and 3 unsupported inventory-only records |
| graphify-present | PASS | 4 derived Graphify files inventoried; semantic route absent |

The bounded workspace discovered exactly five projects in stable sorted order. Nested project markers were not promoted under the default parent-project policy. External symlink escapes and duplicate identity collisions fail closed.

## 7. Classification, authority and projections

Path, filename, heading and Graphify signals are deterministic and retain competing classifications. Configured architecture, requirements, ADR and validation paths receive primary authority; README and roadmap records remain maintained documentation; Graphify and generated records are derived. Documentation maps group records by function, retain source paths and hashes, and expose unsupported, stale and conflict states. Coverage remains categorical and evidence-backed rather than an opaque percentage.

## 8. Sensitive, unsupported and Graphify evidence

Sensitive filenames are metadata-only and their contents are absent from inventory-derived vault artifacts, receipts, errors and CLI JSON. PDF, image and archive records remain visible as inventory-only unsupported records. Graphify discovery and inventory are enabled; classification is `graphify-output`; authority is `derived`; semantic ingestion is disabled; canonical overrides are prohibited.

## 9. Incremental and no-op evidence

The controlled tests prove new-document capture, changed-document revision, deleted-source historical retention, same-content rename detection with path history, and unchanged replay. The unchanged pass reports zero captures, normalizations, verifications, routes and page rewrites. Rename records preserve the old and new paths and the identical-content SHA-256 basis.

## 10. Transaction rollback and retry

Failure injection before promotion restores the previous vault byte-for-byte, leaves ingestion state unadvanced, writes structured failure evidence, and succeeds deterministically after the fault is removed. Strict mode is the golden-fixture default; best-effort remains an explicit CLI policy.

## 11. Performance environment and measurements

Benchmark command: `../.venv/bin/python scripts/benchmark_ingestion.py --output /tmp/as-wp-004-performance.json --runs 5`. The script performs one warm-up followed by five monotonic-clock samples. Environment: Python 3.12.3, Linux 6.18.33.2-microsoft-standard-WSL2 x86_64, WSL2 filesystem under `/tmp`, local mock normalization.

| Dataset | Files | Bytes | Discovery+inventory median | No-op median | Single-file incremental median |
|---|---:|---:|---:|---:|---:|
| small | 13 | 12,351 | 0.00326 s | 0.00271 s | 0.00263 s |
| medium | 151 | 10,751,925 | 0.07426 s | 0.06530 s | 0.07273 s |
| large | 801 | 57,343,275 | 0.35855 s | 0.36087 s | 0.34745 s |

Small first-ingestion median was 16.51281 s (min 16.26837, max 16.76091). Stage medians were capture 2.76967 s, normalize/verify 7.97231 s, and route 5.72732 s. Large hashing throughput was 152.84 MiB/s. The large provisional budgets of 12 s discovery/inventory, 6 s no-op, and 5 s single-file inventory update passed. Hashing is streaming; benchmark staging is temporary and removed at process exit.

## 12. Full validation matrix

| Gate | Exact command/result |
|---|---|
| Stage 2 focused | `python -m pytest tests/test_ingestion_stage2.py -q` — 4 passed |
| AS-WP-004 focused | `python -m pytest tests/test_ingestion.py tests/test_ingestion_stage2.py -q` — 10 passed |
| Full subproject | `../.venv/bin/python -m pytest tests -q` — 129 passed |
| Parent repository | `./.venv/bin/python -m pytest -q` — 54 passed |
| Mypy | `./.venv/bin/python -m mypy src atlas-vault-documentation` — 66 source files, no issues |
| Ruff | `./.venv/bin/python -m ruff check .` — passed |
| Compilation | `./.venv/bin/python -m py_compile atlas-vault-documentation/internal/*.py atlas-vault-documentation/scripts/*.py` — passed |
| CLI help | all four discovery/inventory/ingest/validate help commands — passed |
| Strict validation | `validate_ingestion.py --strict --json` on fixture vaults — passed |
| Performance | benchmark command above — passed provisional budgets |

## 13. Acceptance criteria matrix

| Requirement | Status | Evidence |
|---|---|---|
| AS-021 deterministic bounded discovery | PASS | workspace fixture test and discovery CLI |
| AS-022 complete stable inventory | PASS | inventory tests and benchmark |
| AS-023 classification and authority | PASS | rich/sparse/mixed/Graphify fixture assertions |
| AS-024 governed capture/normalize/verify/router integration | PASS | golden and Stage 2 ingestion tests; routing receipts |
| AS-025 documentation-map projection | PASS | strict validation and fixture vault maps |
| AS-026 evidence-backed coverage | PASS | sparse missing and rich complete/partial evidence |
| AS-027 incremental and true no-op processing | PASS | replay and mutation tests |
| AS-028 changed/deleted/renamed/conflicting handling | PASS | incremental state, conflict and path-history assertions |
| AS-029 Graphify derived-artifact handling | PASS | four-file inventory; no Graphify route event |
| AS-030 strict validation, rollback and immutable receipts | PASS | rollback/retry test, validation reports and receipts |

## 14. Compatibility, residual risks and deferred scope

The implementation is additive to AS-WP-003 and preserves router-only Atlas writes, Python 3.12 strict typing, offline mock operation, source preservation and human-safe generated regions. First ingestion is subprocess-heavy and therefore materially slower than inventory-only operations; this is a bounded pilot observation, not a correctness issue. PyYAML remains an existing runtime dependency for project manifests. Broad semantic conflict resolution, Graphify schema adapters/relationships, and uncontrolled estate scanning are deferred.

## 15. Receipts and updated ATLAS-DOC-RECEIPT

Project ingestion receipts are written under `ingestion/receipts/<project>-<inventory-hash>.json`. The final work-package certification receipt is [ATLAS-DOC-RECEIPT.md](ATLAS-DOC-RECEIPT.md). The benchmark evidence was generated at `/tmp/as-wp-004-performance.json` and is reproducible with the command in §11.

## 16. Stage 3 gate

Certification authorizes only a bounded dry-run pilot: Project Atlas, one mature Python project, one modern TypeScript project, one monorepo, and one sparse or archived project. AS-WP-005 may begin for Graphify adapters only after this certified evidence is reviewed.
