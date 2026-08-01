# AS-WP-005 Certification — Graphify Adapter, Relationship Validation and Derived Projections

## 1. Executive summary

AS-WP-005 CERTIFIED — Graphify artifacts are deterministically validated, resolved, source-linked, quarantined where necessary, and projected as provenance-backed derived Atlas relationships.

The implementation is offline and file-based. It accepts only AS-WP-004 inventory-backed Graphify artifacts whose paths, authority and SHA-256 match inventory state. Canonical Markdown projections pass through the AS-WP-003 router transaction boundary.

## 2. Scope and non-goals

Implemented schema acceptance, JSON/JSONL parsing, canonical nodes and relationships, project-local identity resolution, source-document links, categorical verification/confidence, duplicate collapse, conflict/orphan quarantine, incremental state, deterministic JSONL stores, router-owned Markdown projections, graph-health metrics, strict validation, receipts, CLI tools and benchmarks. Production graph databases, fuzzy/LLM resolution, cross-project graph policy, source-code analysis and estate-wide analytics remain deferred.

## 3. Engineering metrics and files

Added graphify discovery/schema/parser, node/edge models, identity, source-link, confidence, deduplication, conflict, quarantine, state, projection, validation and ingestion modules; four graph CLIs; seven JSON schemas; six contract references; Graphify Stage 2 fixtures and benchmark coverage. The focused graph suite is 5 passed. The subproject suite after the final test addition is 134 passed; the parent suite remains 54 passed.

## 4. Graphify artifact contract and schema matrix

Supported artifact names are `graph.json`, `nodes.json`, `edges.json`, `nodes.jsonl`, `edges.jsonl`, `metadata.json`, `metadata.yaml` and `metadata.yml`. `graphify-1.0` and compatible `schema_version: 1` envelopes are accepted. Metadata files are inventoried and accepted without producing nodes or edges. Unknown schemas, malformed JSON/JSONL, missing records, changed hashes and boundary violations are rejected or quarantined.

## 5. Node and relationship normalization

Nodes retain Graphify IDs, artifact hash, record index, type, label, bounded attributes, authority `derived`, source documents and identity explanation. Relationships retain canonical source/target IDs, original edge ID, source relationship type, artifact provenance, source revisions, verification state, confidence and supporting artifacts. Unknown node and relationship types are preserved as `unknown` or `extension` rather than silently remapped to a known type.

## 6. Identity and source-link behavior

Resolution precedence is explicit Atlas ID → configured mapping → stable project-local identifier → unresolved. No fuzzy matching is used. Source links resolve by document ID or relative path and retain the current document SHA-256. Primary-linked relationships become `verified`; maintained-document links become `supported`; absent links remain `inferred`; missing endpoints become `orphaned` and are quarantined.

## 7. Authority, confidence, duplicates and conflicts

All Graphify records remain `authority: derived`, including verified records. Confidence is categorical and explainable. Identical relationship fingerprints collapse into one canonical record while retaining supporting artifacts. Same-edge or incompatible duplicate mappings create explicit `duplicate-conflict` quarantine records; last-write-wins is not used.

## 8. Quarantine and security

The quarantine store retains category, redacted record fingerprint, provenance and remediation guidance. Covered categories include ambiguous identity, unresolved endpoints, malformed records and duplicate conflicts. Nested secret/token/password/content/private-key fields are removed before quarantine serialization. Project roots and artifact hashes are checked before parsing; source files are never mutated.

## 9. Incremental graph state and no-op replay

`relationships/state/<project-id>.json` stores artifact hashes, canonical nodes, relationships, quarantine and the last receipt. Unchanged artifact hashes return a no-op without reparsing, rewriting stores, rewriting projections or issuing a duplicate receipt. Removed-artifact history remains in the prior state until an explicit retention policy is introduced.

The golden Graphify fixture proved: valid nodes ingested, source-linked relationship verified, duplicate edge collapsed with provenance, inferred edge retained and labeled, orphan edge quarantined, derived authority preserved, and byte-identical no-op replay.

## 10. Canonical stores and projections

Canonical stores are deterministic JSONL under `relationships/nodes/` and `relationships/edges/`; state, quarantine summaries and immutable receipts are under their corresponding `relationships/` directories. `projects/<project-id>/relationships.md` and `graph-health.md` are human-facing projections generated from machine state and promoted through `atlas_router.update_derived_projection`. Mermaid and external graph databases are not required.

## 11. Transaction and rollback evidence

The focused transaction test injects a projection failure before machine-store promotion and confirms that no graph state or success receipt is written. Projection and store preparation occur before the final state/receipt writes. Full rollback journaling for an already-promoted graph-store failure remains a residual hardening item for a future maintenance package.

## 12. Performance baseline

Command: `../.venv/bin/python scripts/benchmark_graphify.py --output /tmp/as-wp-005-performance.json --runs 5`. Environment: Python 3.12.3, Linux 6.18.33.2-microsoft-standard-WSL2 x86_64, WSL2 local temporary filesystem, one warm-up plus five samples using monotonic timers.

| Dataset | Nodes | Edges | Parse median | First-ingestion median | No-op median | Nodes/s | Edges/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| small | 25 | 50 | 0.00017 s | 0.02445 s | 0.00136 s | 1,023 | 2,045 |
| medium | 500 | 2,000 | 0.00429 s | 0.57966 s | 0.04457 s | 863 | 3,450 |
| large | 5,000 | 25,000 | 0.05671 s | 7.92459 s | 0.70032 s | 631 | 3,155 |

No correctness shortcut is used for the benchmark; schema parsing, normalization, identity resolution, source linking, deduplication, projection and validation paths remain active. Peak memory was not instrumented; this is a residual operational observation, not a claimed measurement.

## 13. Validation matrix

| Gate | Result |
|---|---|
| Graph focused tests | `python -m pytest tests/test_graph_ingestion.py -q` — 5 passed |
| Full subproject suite | `../.venv/bin/python -m pytest tests -q` — 134 passed |
| Parent repository suite | `./.venv/bin/python -m pytest -q` — 54 passed |
| Mypy | `./.venv/bin/python -m mypy src atlas-vault-documentation` — 87 source files, no issues |
| Ruff | `./.venv/bin/python -m ruff check .` — passed |
| Compilation | `./.venv/bin/python -m py_compile atlas-vault-documentation/internal/*.py atlas-vault-documentation/scripts/*.py` — passed |
| CLI help | inspect, ingest, rebuild and validate Graphify CLIs — passed |
| Strict graph validation | golden fixture state and projections — passed |
| Performance | 5-run small/medium/large benchmark — passed |

## 14. Acceptance criteria matrix

| Requirement | Status | Evidence |
|---|---|---|
| AS-031 artifact/schema acceptance | PASS | discovery/parser tests and `inspect_graphify.py` |
| AS-032 canonical node normalization | PASS | golden fixture node store and focused ingestion test |
| AS-033 canonical relationship normalization | PASS | edge store, relationship projection and focused test |
| AS-034 deterministic identity resolution | PASS | explicit/project-local resolution path and fixture assertions |
| AS-035 source linkage and verification states | PASS | primary architecture link becomes verified; missing links inferred |
| AS-036 duplicate collapse/conflicts | PASS | duplicate edge collapse and conflict quarantine |
| AS-037 orphan/invalid quarantine | PASS | orphan endpoint and malformed/security quarantine tests |
| AS-038 incremental state/no-op replay | PASS | byte-identical replay test and state store |
| AS-039 provenance-backed projections | PASS | router-owned relationships and graph-health Markdown |
| AS-040 strict validation/rollback/receipts | PASS | validation, injected projection failure, immutable receipt |

## 15. Compatibility and residual risks

AS-WP-005 is additive to AS-WP-004 and leaves Graphify semantic ingestion disabled unless explicitly enabled in configuration. Cross-project edges remain disabled by default. Graph-store promotion is currently ordered after router projection; future hardening should wrap machine stores and projections in one explicit staged transaction with recovery journaling. Peak-memory instrumentation and removed-record re-evaluation are deferred.

## 16. Receipts and next boundary

Each successful run writes `relationships/receipts/<project-id>-<combined-hash>.json`. The certification receipt is recorded in [ATLAS-DOC-RECEIPT.md](ATLAS-DOC-RECEIPT.md). AS-WP-006 may establish global identities and cross-project authority rules; no such behavior is included here.
