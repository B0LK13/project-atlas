# Executable Backlog

## Epic A — Repository foundation

- [x] A-001 Create `pyproject.toml`
- [x] A-002 Create `src/project_atlas`
- [x] A-003 Configure pytest
- [x] A-004 Add ruff and mypy configuration
- [x] A-005 Implement structured logging
- [x] A-006 Add CI workflow
- [x] A-007 Add `atlas --help`

## Epic B — Domain model

- [x] B-001 Implement `SourceRecord`
- [x] B-002 Implement `ConceptRecord`
- [x] B-003 Implement `Claim`
- [x] B-004 Implement `ProvenanceReference`
- [x] B-005 Implement `ConflictRecord`
- [x] B-006 Implement `ValidationFinding`
- [x] B-007 Validate against JSON schemas

## Epic C — Discovery

- [x] C-001 Recursive source scanner
- [x] C-002 Include/exclude configuration
- [x] C-003 MIME and extension detection
- [x] C-004 Streaming SHA-256 hashing
- [x] C-005 Exact duplicate grouping
- [x] C-006 Manifest persistence
- [x] C-007 Unsupported file reporting
- [x] C-008 Path traversal tests

## Epic D — Parsing

- [x] D-001 Markdown parser
- [x] D-002 YAML frontmatter parser
- [x] D-003 Plain-text parser
- [x] D-004 Heading extraction
- [x] D-005 Link extraction
- [x] D-006 Parser registry
- [x] D-007 Malformed input tests

## Epic E — Classification

- [x] E-001 Explicit override rules
- [x] E-002 Path rules
- [x] E-003 Filename rules
- [x] E-004 Frontmatter rules
- [x] E-005 Heading rules
- [x] E-006 Classification method audit field
- [x] E-007 Unknown classification path

## Epic F — Generation

- [x] F-001 Stable ID strategy
- [x] F-002 Frontmatter renderer
- [x] F-003 Project note renderer
- [x] F-004 Source reference renderer
- [x] F-005 Conflict renderer
- [x] F-006 Deterministic ordering
- [x] F-007 Atomic file writes

## Epic G — Human-safe updates

- [x] G-001 Protected marker parser
- [x] G-002 Generated-region replacement
- [x] G-003 Human-region preservation
- [x] G-004 Fail-closed malformed marker handling
- [x] G-005 Golden-file tests

## Epic H — Validation

- [x] H-001 YAML validator
- [x] H-002 Schema validator
- [x] H-003 Link validator
- [x] H-004 Provenance validator
- [x] H-005 Lifecycle validator
- [x] H-006 Freshness validator
- [x] H-007 Orphan validator
- [x] H-008 Secret scanner
- [x] H-009 Coverage validator
- [x] H-010 Severity exit codes

## Epic I — Portfolio intelligence

_Remaining items (I-002 through I-005, I-007, I-008) are implemented
under **AS-MVP-001** on `feat/as-mvp-001-portfolio-pilots`
(implementation complete, acceptance-tested, awaiting independent
verification and owner merge; see
`docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md` and
`docs/evidence/AS-MVP-001-receipt.yaml`). Left unchecked until
independent verification passes and the branch is merged to `main`._

- [x] I-001 Project index generator
- [x] I-002 Portfolio overview — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] I-003 Maturity matrix — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] I-004 Documentation gap report — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] I-005 Stale knowledge report — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] I-006 Conflict review queue
- [x] I-007 Dependency report — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] I-008 Capability report — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge

## Epic J — Incremental operation

- [x] J-001 State cache
- [x] J-002 Added source detection
- [x] J-003 Changed source detection
- [x] J-004 Removed source handling
- [x] J-005 Impact graph
- [x] J-006 Selective regeneration

## Epic K — Pilot onboarding

_Items are implemented under **AS-MVP-001** on
`fix/as-mvp-001-r1-relation-edge-tests` (originally
`feat/as-mvp-001-portfolio-pilots`; see
`docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md` and
`docs/evidence/AS-MVP-001-receipt.yaml`). All of K-001 through K-007 are
now implemented and acceptance-tested (AS-MVP-001-R1 release-closure
remediation: golden manifest/output fixtures for K-004/K-005, an
itemized contradiction checklist for K-006, and a dedicated
credential-shaped canary fixture for K-007). Left unchecked until final
independent verification passes and the branch is merged to `main`._

- [x] K-001 Nebula fixture corpus — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] K-002 Black Agency OS fixture corpus — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] K-003 Dark Factory fixture corpus — implemented, acceptance-tested (AS-MVP-001); pending independent verification/merge
- [x] K-004 Expected manifests — implemented, acceptance-tested (AS-MVP-001-R1); pending independent verification/merge
- [x] K-005 Expected generated vault — implemented, acceptance-tested (AS-MVP-001-R1); pending independent verification/merge
- [x] K-006 Contradiction fixtures — implemented, acceptance-tested (AS-MVP-001-R1); pending independent verification/merge
- [x] K-007 Secret fixtures — implemented, acceptance-tested (AS-MVP-001-R1); pending independent verification/merge

## Cross-cutting follow-up — Atlas Core vertical slice

## Epic L — Repository governance

- [x] L-001 AS-GH-001 GitHub repository governance baseline — tip artifacts present (`GOVERNANCE.md`, `VERSIONING.md`, `RELEASING.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, issue templates, README nav, additive governance tests, `docs/adr/ADR-006-github-repository-governance-baseline.md`, `docs/work-packages/AS-GH-001.md`, `docs/evidence/AS-GH-001-receipt.yaml`); docs reconciliation on `feat/as-l-001-governance-close` — **GOVERNOR REQUIRED**; live settings activation deferred (AS-GH-002 owner-gated).

- [x] CORE-MODEL-001 Integrate `ConceptRecord`, `Claim`, and
  `ProvenanceReference` into formal project projections and richer validated
  project frontmatter — **CLOSED — SATISFIED BY** MODEL-001A + 001B + 001C on tip
  per `PROJECT-ATLAS-1.0-RECONCILED-STATE.md`. Residual richer frontmatter polish
  is optional deferred, not a reopen.
- [x] AS-INGEST-MANIFEST-001 Multi-batch discovery snapshot and ingest-report
  merge by `source_id` — implementation complete on
  `feat/as-ingest-manifest-001` (closes AS-MVP-001 accepted overwrite debt;
  governor review required; not self-certified).
- [x] CORE-OPS-001 Add explicit read-before-write/hash-before-replace
  accounting and evidence for filesystem-write suppression on unchanged
  replay. Keep `content drift` and `canonical content changes` distinct from
  physical filesystem writes. (AS-CORE-OPS-001 on
  `feat/as-core-ops-001-promote-accounting` — governor review required; not
  self-certified.)
- [x] AS-BACKUP-001 Verified Atlas Snapshot (fixture restore; cold D1-D4+D6; ops durability ≠ authority)
- [x] AS-DEMO-2.2-RECOVERY-ID-001 Fresh product bootstrap establishes canonical
  `.atlas/vault.json` so stranger/demo pipelines are recovery-capable without
  weakening snapshot/restore identity trust (D-PROJECT-ATLAS-CLOUD-DEMO-RECOVERY-019)
- [x] CORE-SEC-001 Implement content-based secret detection and redaction for
  pilot ingestion. Filename-only sensitive-file detection must not be treated
  as sufficient for real-project ingestion.

## AS-INT-001 — Governed agent-event ingestion

- [x] INT-001 Define versioned shared event/provenance/receipt contracts
- [x] INT-002 Discover and classify Control Plane event packages
- [x] INT-003 Revalidate packages at Core ingestion boundary
- [x] INT-004 Generate project activity and session projections
- [x] INT-005 Quarantine invalid, pending and conflicting packages
- [x] INT-006 Prove deterministic replay and strict public CLI workflow
- [x] INT-007 Independent integration certification
- [x] INT-008 Bind event skill identity to a trusted Vault policy
- [x] INT-009 Define raw-package and receipt retention policy
- [x] INT-010 Preserve removed-package/deletion state in projections
  (AS-INT-010 tip-safe tombstone projection on
  `feat/as-int-010-tombstones`; IMPLEMENTATION COMPLETE — GOVERNOR REQUIRED)
- [x] INT-011 Define receipt revocation and invalidation semantics
  (AS-INT-011 tip-safe operational index under
  `generated/ops/receipt-revocations.json`; never Layer B / never authority)
- [x] INT-012 Define schema migration and compatibility tooling
  (AS-INT-012 tip-safe compat/migrate-dry-run report under
  `generated/ops/schema-compat-report.json`; never Layer B / never authority)
- [ ] INT-013 Run the bounded multi-project integration pilot

## AS-CORE-002 — Semantic domain model and source lifecycle hardening

- [x] CORE2-001 Add strict versioned Project, source lifecycle, authority,
  coverage, validation, decision, work-package and agent-event reference models
- [x] CORE2-002 Add semantic record schema and schema validation coverage
- [x] CORE2-003 Compile deterministic rich project metadata and coverage
- [x] CORE2-004 Preserve human regions and fail closed on malformed markers
- [x] CORE2-005 Add content-based secret findings with metadata-only output
- [x] CORE2-006 Persist source lifecycle state and deletion tombstones
- [x] CORE2-007 Complete ConceptRecord/Claim projection composition and migrations
  — **CLOSED — SATISFIED BY** MODEL-001A/B/C composition on tip per
  `PROJECT-ATLAS-1.0-RECONCILED-STATE.md`. Stale “001B pending merge” prose
  **SUPERSEDED**.
- [x] CORE2-008 Add duplicate-source conflict projections and authority review queue
  (AS-CORE2-008 tip-safe residual on `feat/as-core2-008-review-queue`; IMPLEMENTATION COMPLETE — GOVERNOR REQUIRED)
- [x] CORE2-009 Add interrupted-write recovery and complete write accounting
  (AS-CORE2-009 tip-safe crash orphan recovery on
  `feat/as-core2-009-promote-recovery`; IMPLEMENTATION COMPLETE — GOVERNOR REQUIRED;
  contract refresh under D-PROJECT-ATLAS-WEB-AND-1.0-AUTONOMOUS-COMPLETION-001)
- [x] CORE2-010 Run controlled pilot lifecycle certification
  (AS-CORE2-010 fixture-safe matrix; estate_pilot_passed=false)

## AS-ID-001 — Durable Source Lineage Identity

- [x] ID-001 Add UUIDv4 project genesis with injected test providers
- [x] ID-002 Add Core-local project identity synchronization
- [x] ID-003 Add source registry v2 and durable lineage derivation
- [x] ID-004 Add canonical path and raw-byte fingerprint contracts
- [x] ID-005 Add atomic v1-to-v2 migration receipts
- [x] ID-006 Add duplicate-identity and ambiguity fail-closed checks
- [x] ID-007 Add replay, rollback, concurrency, and schema validation tests
- [x] ID-008 Governor review and independent certification

## AS-CORE-003 — Claim Identity v2 remediation

_Status: V2-003 was preserved and rejected by independent review. V2-004 implemented and validated the remediation but was superseded before review because its immutable tag annotation recorded an invalid tree string. V2-005 passed a fresh isolated review with three non-blocking findings on 2026-08-05, but its PR head failed ubuntu CI on platform-dependent `media_type` detection and K-004 fixture newline translation. V2-006 fixes both determinism defects additively, passed an isolated review addendum, and is green on Windows and Linux gates. Remote CI verification and Project Owner merge authorization remain pending._

- [x] CORE3-001 Finalize Claim Identity v2 formula using raw stable semantic locator
- [x] CORE3-002 Use `event:{event_id}` locator for agent-event-derived claims
- [x] CORE3-003 Restore ingestion project identity locks
- [x] CORE3-004 Fix OCC compare-and-swap `None` precondition handling
- [x] CORE3-005 Rewrite v1-to-v2 migration as self-contained, schema-validated, atomic, idempotent module
- [x] CORE3-006 Record ambiguous v1-to-v2 mappings instead of guessing
- [x] CORE3-007 Add `claim-alias` schema and register it
- [x] CORE3-008 Regenerate dependency-report.json golden fixture after identity-formula change
- [x] CORE3-009 Add concurrency, migration, historical-completeness and alias-schema tests
- [x] CORE3-010 Mark all `tests/integration/*.py` modules with `pytest.mark.integration`
- [x] CORE3-011 Add canonical JSON-array identity serialization to close F-001
- [x] CORE3-012 Enforce mutually-exclusive resolved/ambiguous alias collections to close F-002
- [x] CORE3-013 Extract shared `project_atlas.claim_identity` rules module for compiler/migration parity
- [x] CORE3-014 Normalize CRLF to LF before hashing text sources (cross-platform identity stability)
- [x] CORE3-015 Author ADR-007 for Claim Identity v2 canonicalization
- [x] CORE3-016 Regenerate K-004/K-005 golden fixtures for canonical identity and source-lineage changes
- [x] CORE3-017 Preserve the V2-003 independent-review failure and exact findings
- [x] CORE3-018 Reconstruct real v1 identities from ingested source/lineage/project evidence
- [x] CORE3-019 Scan all supported text evidence and share architecture fallback semantics
- [x] CORE3-020 Isolate migration state per safe project component
- [x] CORE3-021 Commit alias state and its receipt as one validated atomic bundle
- [x] CORE3-022 Reject incomplete, cross-project, or resolved/ambiguous replay state
- [x] CORE3-023 Add tested cross-file promotion rollback and artifact cleanup
- [x] CORE3-024 Preserve the malformed V2-004 annotation and supersede it without moving the tag
- [x] CORE3-025 Complete a fresh independent V2-005 review and certification
- [x] CORE3-027 Remediate ubuntu CI platform determinism (media types, K-004 fixture) and cut V2-006
- [ ] CORE3-026 Merge to `main`

## AS-EXT-001A — Structured evidence parsers, locator refinement, and compilation-status reporting

_Status: implementation complete through Level 0 self-host evidence. Directive D-PROJECT-ATLAS-KIMI-AS-EXT-001A-001; base `6d874751d3ed9cb05433a8d50ab372a997418d84`; addresses measured P0 failures (batch abort on first of 29 flat-YAML locator failures, 2 heading-locator collisions, 15 verified claims, 0 explicit anchors). Package contract: `docs/work-packages/AS-EXT-001A.md`. Self-host receipt: `docs/evidence/AS-EXT-001A-level0-selfhost-receipt.yaml`. Adversarial remediation complete (blocking locator-collision isolation fix + five concerns, commit 33bc65a); candidate re-frozen V2 with reconciled re-run — receipt `docs/evidence/AS-EXT-001A-level0-selfhost-receipt-v2.yaml` (supersedes V1, preserved)._

- [x] EXT1A-001 Create AS-EXT-001A package specification and confirm implementation baseline gates
- [x] EXT1A-002 Materialize frozen fixtures (real F-01…F-08 with provenance + authored synthetic cases, directive §9)
- [x] EXT1A-003 Implement compilation outcome state machine (§7.8: COMPLETE_CANDIDATE / PARTIAL_CANDIDATE / FAILED / PROMOTION_FAILED / COMPLETE)
- [x] EXT1A-004 Implement frozen Pydantic v2 parser-output contract (§7.2; no final claim identity in parser output)
- [x] EXT1A-005 Implement specific-first classification precedence (§7.1; keywords must not override structural classification)
- [x] EXT1A-006 Implement safe YAML parsing and `yamlpath:` locators (§7.4; NFC normalization, duplicate-key diagnostics)
- [x] EXT1A-007 Implement evidence receipt profiles (§7.5; concept mapping + profile adapters + unknown-field preservation)
- [x] EXT1A-008 Implement registered VERIFY structured profile (§7.6; zero collision, zero abort)
- [x] EXT1A-009 Remediate heading-locator collisions (§7.7; both official collision fixtures)
- [x] EXT1A-010 Implement structured diagnostic model (§7.9; no silent drop)
- [x] EXT1A-011 Implement locator-refinement alias handling via existing v2 mechanism (§7.10; one-to-one only)
- [x] EXT1A-012 Enforce security bounds (§8; safe loading, duplicate keys, bounded nesting/aliases/nodes/size)
- [x] EXT1A-013 Record self-host evidence: RAW corpus Level 0 + product metrics (§12/§13)
- [x] EXT1A-020 All 31 real receipts structurally parse with a support/profile status (§10 MUST)
- [x] EXT1A-021 One bad source does not prevent extraction from independent good sources (§10 MUST)
- [x] EXT1A-022 PARTIAL candidate never alters canonical state; COMPLETE alone may promote; promotion failure rolls back (§10 MUST)
- [x] EXT1A-023 Deterministic repeat produces byte-identical candidate output (§10 MUST)
- [x] EXT1A-024 Claim Identity v2 tests remain green; compiler and migration remain consistent (§10 MUST)
- [x] EXT1A-025 Aliases promoted only for provable one-to-one mappings; one-to-many remain ambiguous (§10 MUST)
- [x] EXT1A-026 Source/parser provenance on every emitted claim; claim counts from canonical JSON cross-checked (§10 MUST)

## AS-CORE-008 — Subject Multi-Field Knowledge Query

_Status: implementation complete on `feat/as-core-008-subject-multifield-query`; awaiting governor review / merge. Governing contract: query-scope-lock `AS-CORE-008-PACKAGE-CONTRACT.md`. Base `d209b359ddd30e75e4709932fd55cb9b71016927`. Additive read-only composition over AS-CORE-007; persistence NONE; authority/temporal CONSUME-ONLY._

- [x] CORE8-001 Domain envelope `KnowledgeMultiFieldAnswer` + JSON schema
- [x] CORE8-002 Library `query_knowledge_fields` (single snapshot; point-builder reuse)
- [x] CORE8-003 CLI adapter (repeatable `--field` / `--fields`; point path preserved)
- [x] CORE8-004 Focused FR/INV suite (ordering, duplicates, snapshot fail-closed, parity, no-mutation)
- [x] CORE8-005 Package guide `docs/AS-CORE-008-subject-multifield-query.md`
- [ ] CORE8-006 Governor review and merge to `main`

## AS-QUERY-DIAG-001 — Structured Query Outcome Diagnostics

_Status: implementation complete on `feat/as-query-diag-001`; awaiting governor review. MERGE NO. Directive `D-PROJECT-ATLAS-FORWARD-PIPELINE-ACTIVATION-001`. Frozen contract: orphans `gen4-next-wave-parallel-001/AS-QUERY-DIAG-001-CONTRACT.md`. Base `9f656ab` / tree `20882c55`. Additive diagnostics only; success-path 007/008 JSON default-stable; `knowledge_compiler` / Graph / MODEL FORBIDDEN._

- [x] QDIAG-001 Domain `QueryDiagnostic` + outcome classes + JSON schema
- [x] QDIAG-002 Library classifiers / serializers (`classify_query_outcome`, `query_diagnostic_from_*`)
- [x] QDIAG-003 CLI structured stdout on `KnowledgeQueryError` (exit 1); argparse exit 2 unchanged
- [x] QDIAG-004 Focused T01–T12 suite `tests/unit/test_as_query_diag_001.py`
- [x] QDIAG-005 Package guide + 007/008 cross-links
- [ ] QDIAG-006 Governor review and merge to `main`

## AS-WEB-001 — Atlas Web Application foundation

_Status: **MERGED** via PR #53 (`bcd453f`). Directive `D-PROJECT-ATLAS-WEB-AND-1.0-AUTONOMOUS-COMPLETION-001`. Firewall: `apps/web/**` + `src/project_atlas/web_api/**` + ADR-008. UI ≠ canonical; Graph ≠ authority; Unknown ≠ healthy. NO vault truth writes; NO REL-001; NO PILOT invent. **WEB APPLICATION ACCEPTED = NO** (foundation only)._

- [x] WEB001-001 ADR-008 Vite+React architecture + read-first API boundary
- [x] WEB001-002 Scaffold `apps/web` runnable shell + smoke script
- [x] WEB001-003 `project_atlas.web_api` read-only adapters (projects / OBS health consume)
- [x] WEB001-004 Orphan design-lab note (4 prototype themes)
- [x] WEB001-005 Focused pytest `tests/unit/test_as_web_001_*.py`
- [x] WEB001-006 Governor review and merge to `main`

## AS-WEB-002 — Design-lab prototypes + shared tokens

_Status: implementation complete on `feat/as-web-002-design-lab`; awaiting governor review / merge. Base tip at open: `bcd453f` / TREE `0afe3218`. Firewall: **`apps/web/**` + ADR-009 + soft WORKLOG/backlog only** — zero `src/project_atlas` mutation. UI ≠ canonical; Graph ≠ authority; Unknown ≠ healthy. **WEB APPLICATION ACCEPTED = NO** (design-lab only)._

- [x] WEB002-001 Four HashRouter design-lab prototype routes (Ledger Desk / Signal Rack / Cartograph Quiet / Terminal Honest)
- [x] WEB002-002 Shared `tokens.css` `--atlas-*` tokens + `[data-theme]` remaps
- [x] WEB002-003 ADR-009 web design tokens
- [x] WEB002-004 Smoke script covers design-lab routes
- [x] WEB002-005 Soft WORKLOG + backlog checklist
- [x] WEB002-006 Governor review and merge to `main`

## AS-WEB-003 — Production shell + Command Center + ADR-010

_Status: implementation complete on `feat/as-web-003-production-shell`; awaiting governor review / merge. Tip base `6c74b91`. Firewall: `apps/web/**` + ADR-010 + soft WORKLOG/backlog. UI ≠ canonical; Graph ≠ authority; Unknown ≠ healthy. **WEB APPLICATION ACCEPTED = NO**._

- [x] WEB003-001 ADR-010 / ADR-ATLAS-WEB-UX-001 (production vs design-lab; Command Center modes)
- [x] WEB003-002 Production routes: Home / Projects / Ops / Command Center
- [x] WEB003-003 Command Center mode switcher (overview · projects · ops · impact)
- [x] WEB003-004 Preserve design-lab routes; smoke extended
- [x] WEB003-005 Soft WORKLOG + backlog checklist
- [ ] WEB003-006 Governor review and merge to `main`
- [ ] WEB003-007 WEB APPLICATION ACCEPTED criteria package (later — not this PR)

## AS-OPT-GATE-001 — Governed experiment and promotion boundary

_Status: **MERGED** via PR `#321` (`c0ebd46` on `main`). Directives `D-PROJECT-ATLAS-OPT-GATE-027` + `D-PROJECT-ATLAS-OPT-GATE-REMEDIATE-030` + D-031 residual closed under `D-PROJECT-ATLAS-CLOUD-AUTONOMOUS-E2E-032`. Reuses AS-2.2-EVAL-001 + AS-2.2-EVAL-BROKER-001. Does **not** wake Atlas-OPT, AutoLab, RL, or Prime. `ATLAS_OPT_WAKE_GATE = CLOSED` (runtime). `EVALUATOR_STABLE = YES`; wake recommendation `OPEN_ELIGIBLE` (governance only; AutoLab not activated)._

- [x] OPTGATE-001 Typed hard-gate contract (PASS/FAIL only; gates precede score)
- [x] OPTGATE-002 Sealed experiment envelope + mid-run immutability verify
- [x] OPTGATE-003 Privacy-safe reconstructable experiment receipt
- [x] OPTGATE-004 Promotion engine (`PROMOTE_ELIGIBLE` / `REJECT` / `INVALID_EXPERIMENT`)
- [x] OPTGATE-005 Anti-gaming A–G + fail-closed + security IV tests
- [x] OPTGATE-007 Honesty-catalog object seal + receipt threshold binding (IV remediate-030)
- [x] OPTGATE-008 Sealed anchors required to certify `PROMOTE_ELIGIBLE` (closes threshold-downgrade redigest)
- [x] OPTGATE-006 Independent IV PASS + merge to `main`
- [x] OPTGATE-009 Post-merge evaluator reassessment (D-032): `EVALUATOR_STABLE = YES`; wake recommendation `OPEN_ELIGIBLE` (governance only — runtime `ATLAS_OPT_WAKE_GATE` remains `CLOSED`; AutoLab not activated)

## Coder Alpha (D-PROJECT-ATLAS-CODER-ALPHA-035 / D-037)

_North star: persistent brain for AI-native projects. Durable anchor:
`docs/product/CODER-ALPHA-NORTH-STAR.md`. Rebase table:
`docs/CODER-ALPHA-035-REBASE.md`. Historical roadmap/backlog items below
Epic K remain evidence; they do not override Coder Alpha owner priority._

- [x] AS-CODER-ALPHA-CONNECT-001 `atlas connect .` one-command bind+compile
- [x] AS-CODER-ALPHA-OVERVIEW-001 Project Overview lens
- [x] AS-CODER-ALPHA-STATE-001 Current State lens
- [x] AS-CODER-ALPHA-CHANGED-001 What Changed defaults
- [x] AS-CODER-ALPHA-DECISIONS-001 Decision memory
- [x] AS-CODER-ALPHA-UNKNOWN-001 Unknown/conflict bundle
- [x] AS-CODER-ALPHA-BRIEF-001 Unified project brief (`atlas brief`)
- [x] AS-CODER-ALPHA-CAPTURE-001 Session capture defaults
- [x] AS-CODER-ALPHA-HANDOFF-001 `atlas handoff` create/resume
- [x] AS-CODER-ALPHA-CONTEXT-001 Agent context export
- [x] AS-CODER-ALPHA-OBSIDIAN-001 Living Obsidian projection
- [x] AS-CODER-ALPHA-HUMAN-LOOP-001 Human decisions → Truth Core
- [x] AS-CODER-ALPHA-WEB-001 Web Knowledge UX on Core
- [x] AS-CODER-ALPHA-TRUTH-UX-001 Evidence/conflict/UNKNOWN inspection
- [x] AS-CODER-ALPHA-ARCH-001 Architecture summary from plan/AGENTS (≠ purpose echo)
- [x] AS-CODER-ALPHA-CHANGED-002 Second-connect What Changed / stale-context measure

