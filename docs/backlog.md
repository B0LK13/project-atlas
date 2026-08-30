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

_Remaining items (I-002 through I-005, I-007, I-008) were implemented
under **AS-MVP-001** on `feat/as-mvp-001-portfolio-pilots` and are
**merged**: that candidate (`da04bd31`) is an ancestor of `main`, and
later mainline work has evolved the implementation (AS-MVP-001-R1 and
subsequent packages). There is no outstanding merge of that candidate,
and the branch name above is historical rather than a pending
integration target. The four portfolio capabilities were re-verified
against `main` `f1b52565` on 2026-08-27 through the real CLI pipeline
(`init` -> `discover` -> `ingest` -> `build-indexes` ->
`build-portfolio` -> `validate`). See
`docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md` and
`docs/evidence/AS-MVP-001-receipt.yaml` -- that receipt is historical
evidence pinned to the pre-merge candidate and does not certify current
`main` (see its status-reconciliation block)._

- [x] I-001 Project index generator
- [x] I-002 Portfolio overview — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] I-003 Maturity matrix — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] I-004 Documentation gap report — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] I-005 Stale knowledge report — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] I-006 Conflict review queue
- [x] I-007 Dependency report — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] I-008 Capability report — implemented, acceptance-tested (AS-MVP-001); merged to `main`

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
credential-shaped canary fixture for K-007). This work is merged to
`main`; the branches named above are historical rather than pending
integration targets._

- [x] K-001 Nebula fixture corpus — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] K-002 Black Agency OS fixture corpus — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] K-003 Dark Factory fixture corpus — implemented, acceptance-tested (AS-MVP-001); merged to `main`
- [x] K-004 Expected manifests — implemented, acceptance-tested (AS-MVP-001-R1); merged to `main`
- [x] K-005 Expected generated vault — implemented, acceptance-tested (AS-MVP-001-R1); merged to `main`
- [x] K-006 Contradiction fixtures — implemented, acceptance-tested (AS-MVP-001-R1); merged to `main`
- [x] K-007 Secret fixtures — implemented, acceptance-tested (AS-MVP-001-R1); merged to `main`

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

_Status: **MERGED** via the PR #5 platform merge commit `6d874751d3ed9cb05433a8d50ab372a997418d84` (candidate V2-006). Phantom-work correction 2026-08-28: this section still read "Remote CI verification and Project Owner merge authorization remain pending" and CORE3-026 was unchecked, despite the merge commit being a genuine ancestor of current `main` (confirmed via `git merge-base --is-ancestor`) and the code being live -- `claim_identity.py` exists and is imported by both `knowledge_compiler.py` and `evidence_compiler.py`, not stub text. A separate post-merge closure record (docs commit `f7837377`, "AS-CORE-003 post-merge closure record") correctly reconciled this checkbox once already, but that commit is not itself an ancestor of current `main` (confirmed via the same check) -- its `docs/evidence/AS-CORE-003-post-merge-receipt.yaml` does not exist on this branch -- so this correction is re-applied directly here rather than assumed from that lost commit. V2-003 was preserved and rejected by independent review. V2-004 was superseded before review because its immutable tag annotation recorded an invalid tree string. V2-005 passed a fresh isolated review with three non-blocking findings but failed ubuntu CI on platform-dependent `media_type` detection and K-004 fixture newline translation. V2-006 fixed both determinism defects additively, passed an isolated review addendum, and was green on Windows and Linux gates. Non-blocking V2-005 findings are routed to the parser roadmap as follow-ups._

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
- [x] CORE3-026 Merge to `main` (commit `6d874751d3ed9cb05433a8d50ab372a997418d84`; phantom-work correction 2026-08-28)

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

_Status: **MERGED** via PR #14 (`59670bf33feede82dd85daa3da994f410a8d838e`, 2026-08-08). Phantom-work correction 2026-08-28: this section still read "awaiting governor review / merge" and CORE8-006 was unchecked despite the PR having merged three weeks prior -- corrected directly against `main`, confirmed both via `git merge-base --is-ancestor` (the merge commit is a genuine ancestor of current `main`) and directly against real code (`query_knowledge_fields` imported and called from `cli.py`, not stub text). Governing contract: query-scope-lock `AS-CORE-008-PACKAGE-CONTRACT.md`. Base `d209b359ddd30e75e4709932fd55cb9b71016927`. Additive read-only composition over AS-CORE-007; persistence NONE; authority/temporal CONSUME-ONLY._

- [x] CORE8-001 Domain envelope `KnowledgeMultiFieldAnswer` + JSON schema
- [x] CORE8-002 Library `query_knowledge_fields` (single snapshot; point-builder reuse)
- [x] CORE8-003 CLI adapter (repeatable `--field` / `--fields`; point path preserved)
- [x] CORE8-004 Focused FR/INV suite (ordering, duplicates, snapshot fail-closed, parity, no-mutation)
- [x] CORE8-005 Package guide `docs/AS-CORE-008-subject-multifield-query.md`
- [x] CORE8-006 Governor review and merge to `main` (PR #14, merged 2026-08-08; phantom-work correction 2026-08-28)

## AS-QUERY-DIAG-001 — Structured Query Outcome Diagnostics

_Status: **MERGED** via PR #21 (`e3b5b6b33a0b7c320dc9f902a9025da3476234e1`, 2026-08-09). Phantom-work correction 2026-08-28: this section still read "awaiting governor review, MERGE NO" and QDIAG-006 was unchecked despite the PR having merged three weeks prior -- corrected directly against `main`, confirmed both via `git merge-base --is-ancestor` and directly against real code (`classify_query_outcome` defined and used in `knowledge_query.py`, not stub text). Directive `D-PROJECT-ATLAS-FORWARD-PIPELINE-ACTIVATION-001`. Frozen contract: orphans `gen4-next-wave-parallel-001/AS-QUERY-DIAG-001-CONTRACT.md`. Base `9f656ab` / tree `20882c55`. Additive diagnostics only; success-path 007/008 JSON default-stable; `knowledge_compiler` / Graph / MODEL FORBIDDEN._

- [x] QDIAG-001 Domain `QueryDiagnostic` + outcome classes + JSON schema
- [x] QDIAG-002 Library classifiers / serializers (`classify_query_outcome`, `query_diagnostic_from_*`)
- [x] QDIAG-003 CLI structured stdout on `KnowledgeQueryError` (exit 1); argparse exit 2 unchanged
- [x] QDIAG-004 Focused T01–T12 suite `tests/unit/test_as_query_diag_001.py`
- [x] QDIAG-005 Package guide + 007/008 cross-links
- [x] QDIAG-006 Governor review and merge to `main` (PR #21, merged 2026-08-09; phantom-work correction 2026-08-28)

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
- [ ] AS-CODER-ALPHA-FRESH-AGENT-CHALLENGE-V2 machine-scored fixture harness (current-main; do not retarget #375; HARNESS!=AUTHENTIC_PILOT; MERGE_AUTHORIZATION NOT_GRANTED)
- [x] AS-CODER-ALPHA-WORKFLOW-METRICS-001 honest North Star telemetry from ops receipts (current-main; do not retarget #377; TELEMETRY!=TRUTH CORE; independently verified 2026-08-28, `PASS_WITH_NONBLOCKING_FINDINGS` -- see WORKLOG "EOD convergence wave"; MERGE_AUTHORIZATION NOT_GRANTED)
- [x] AS-CODER-ALPHA-OBSIDIAN-001 Living Obsidian projection
- [x] AS-CODER-ALPHA-HUMAN-LOOP-001 Human decisions → Truth Core
- [x] AS-CODER-ALPHA-WEB-001 Web Knowledge UX on Core
- [x] AS-CODER-ALPHA-TRUTH-UX-001 Evidence/conflict/UNKNOWN inspection
- [x] AS-CODER-ALPHA-ARCH-001 Architecture summary from plan/AGENTS (≠ purpose echo)
- [x] AS-CODER-ALPHA-CHANGED-002 Second-connect What Changed / stale-context measure
- [x] AS-CODER-ALPHA-CHANGED-002b Positive-delta add/mod/remove + self-churn exclusion
- [x] AS-CODER-ALPHA-ATTENTION-001 Attention hygiene classifier (`atlas attention`)
- [x] AS-CODER-ALPHA-ARCH-002 Structured architecture lens (multi-slot, honest UNKNOWN)
- [x] AS-CODER-ALPHA-CROSS-SURFACE-001 Disk/Web/Obsidian/Agent brief consistency tests
- [x] AS-CODER-ALPHA-HUMAN-LOOP-V2 Decide → rematerialize → no pending resurrection
- [x] AS-CODER-ALPHA-SOURCE-HEALTH-001 Source failure explainability (`atlas source-health`)
- [x] AS-CODER-ALPHA-DECISIONS-002 Decision status labels (active/superseded/…)
- [x] AS-CODER-ALPHA-DECISIONS-003 ACTIVE_GOVERNING authority gate
- [x] AS-CODER-ALPHA-ATTENTION-002 care_about triage + source-failure collapse
- [x] AS-CODER-ALPHA-CHANGED-003 semantic know_about narrative
- [x] AS-CODER-ALPHA-ARCH-FIDELITY-001 exact module/path identifiers
- [x] AS-CODER-ALPHA-044-HIGH D-041 Windows/adversarial HIGH truth/isolation remediations (independently verified 2026-08-28, isolation/truth-boundary claims `PASS`; the LIVE_API IPv6-loopback-bind P1 fix in PR #628 **merged to `main`** 2026-08-28T15:50:48Z as `33fb4fad`, confirmed a real ancestor of current `main` via `git merge-base --is-ancestor`; checkbox updated 2026-08-30 during D-PHASE2A post-merge DAG reconstruction -- see WORKLOG "EOD convergence wave")
- [x] AS-ATLAS3-FREEZE-GUARD-001 certified-surface freeze guard hosted-CI blind-spot remediation (PR #630, 5 rounds, independently re-verified PASS across all 5, **merged to `main`** 2026-08-28T15:51:46Z as `264248ba`, confirmed a real ancestor of current `main`; checkbox updated 2026-08-30 during D-PHASE2A post-merge DAG reconstruction; see WORKLOG "PR #630 -- Atlas-3 freeze guard hosted-CI blind spot"). The guard's own correctness is now live on `main`. This does **not** by itself grant the separate Atlas-3 freeze exception `api_server.py` may still need for any future certified-surface change -- that remains a distinct, separately-gated owner decision, unaffected by this checkbox.
- [x] AS-CODER-ALPHA-D049-AUTHORIZED-VOLUME-ROOT-001 CLOSED (merge c282f2c; D-088 authentic PASS; post-merge seal PASS)
- [x] AS-CODER-ALPHA-CAPTURE-002 Conversational capture CLOSED (D-042; merge 9441b0c; D-096 post-hoc owner ratification GRANTED; PRE_MERGE_AUTHORIZATION_PROVENANCE UNVERIFIED; do not rewrite as pre-merge authorization; do not reopen #344)
- [x] AS-2.1-MCP-BRIEF-001 zero-arg `atlas.brief.read` MCP tool (vault-scoped Coder Alpha briefs; MCP!=authority; no request args)
- [x] AS-CODER-ALPHA-REPORT-READ-CONVERGENCE-001 consume-only union of #593-#603, originally on branch `cursor/aug26-report-read-convergence-f3ff` (`next/changed/overview/decisions/unknown/state/architecture/roadmap/portfolio/bitemporal/index-status`). Phantom-work correction 2026-08-28: `CONVERGED_ON_BRANCH != SATISFIED_ON_MAIN` no longer holds -- all 11 `/v1/*-status` API routes are registered in `api_server.py` and all 11 `atlas.*.read` MCP tools are registered in `mcp_registry.py` on current `main`, verified directly (not assumed) against real route/tool handler code, not stub text. EMPTY/UNKNOWN still stay not-healthy on main. This checkbox tracked landing on main, not any further merge authorization.
- [x] AS-CODER-ALPHA-INCREMENTAL-CONNECT-001 no-change reconnect must not double discover+ingest. Phantom-work correction 2026-08-28: implemented and wired on current `main` -- `connect.py` names this package directly in its own docstring and contains `_finish_no_change_reconnect()`; `evaluate_incremental_reconnect()` is defined in `incremental_connect.py` and imported/called from `connect.py`'s real `connect` flow, verified directly against the code (not stub text). Origin PR #374 is merged.
- [x] AS-CODER-ALPHA-NEXT-001 What Next daily lens (`atlas next`; compose attention/roadmap/unknown/source-health; NEXT!=command; independent of AS-2.0-NEXT-001)
- [x] AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001 frozen-at-write estate vs later live estate (does not retarget #378; does not duplicate #419; independently verified 2026-08-28, `PASS_WITH_NONBLOCKING_FINDINGS` -- see WORKLOG "EOD convergence wave"; MERGE_AUTHORIZATION NOT_GRANTED)
- [x] AS-PROJECT-ROADMAP-001 Living Project Roadmap V1 (derived; ROADMAP!=canonical; CLI/API/Web/connect/handoff; D-098 Web context remediation on #354; ROADMAP_STATE=LOCAL_RECERTIFICATION_PENDING; CLOUD_IV=PASS; ROADMAP_LOCAL_AUTHENTIC_IV=BASIC_RECHECK_PASS_2026-08-28 (34/34 current test suite reconfirmed passing against current main -- a basic recheck, not a fresh full adversarial IV matching the 2026-08-28 EOD convergence wave's other packages; see WORKLOG); MERGE_ELIGIBLE=NO; MERGE_AUTHORIZATION NOT_GRANTED)

## AS-ORCH-001A — Agent Result Contract + Deterministic Transition Classification

_Status: **IMPLEMENTED — READY FOR OWNER MERGE GATE** (independently verified 2026-08-28, see WORKLOG "ORCH001A-007"; `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md); not yet merged; not production-ready). Classifies the next eligible transition from a structured `AgentResultEnvelope`. Does **not** dispatch, route automatically, create Cursor hooks, merge, or grant owner authority. `execution_authorized = false` always._

Honesty (mandatory):

- `STRUCTURED RESULT CONTRACT = IMPLEMENTED`
- `DETERMINISTIC CLASSIFICATION = IMPLEMENTED`
- `AUTOMATIC ROUTING = NOT YET IMPLEMENTED`
- `CURSOR HOOK = NOT YET IMPLEMENTED`
- `AGENT DISPATCH = NOT YET IMPLEMENTED`
- `AUTONOMOUS LOOP = NOT YET IMPLEMENTED`
- `AUTOMATIC MERGE = NOT IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`

- [x] ORCH001A-001 `AgentResultEnvelope` model + shipped JSON schema
- [x] ORCH001A-002 `OrchestrationDecision` (`execution_authorized=false`, `merge_authorized=false`)
- [x] ORCH001A-003 Deterministic transition classifier + explicit precedence
- [x] ORCH001A-004 Owner gate (`MERGE_ELIGIBLE` → `OWNER_REQUIRED`, never `MERGE`)
- [x] ORCH001A-005 Read-only CLI `atlas orchestrator validate-result`
- [x] ORCH001A-006 Focused unit tests + schema/model parity
- [x] ORCH001A-007 Independent integration verification (2026-08-28: 118 existing tests re-run PASS + 7 black-box CLI probes, 1 baseline + 6 adversarial, against `main` `718f2beb`, see WORKLOG "ORCH001A-007"; PASS)
- [x] ORCH001A-008 Owner-authorized activation: `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md; consumes existing owner authorization, does not re-merge code, does not grant automatic merge to the loop)
- [x] ORCH001B Policy Router — see AS-ORCH-001B (routing policy implemented; runtime automatic routing NOT implemented)
- [x] ORCH001C Cursor Integration — see AS-ORCH-001C (bridge + optional stop-hook adapter + explicit completion transport; authentic Cursor stop delivery ENVIRONMENT_DEPENDENT; dispatch NOT implemented)
- [x] ORCH001D Agent Dispatcher — see AS-ORCH-001D (fresh current-main single-hop; not #396)
- [x] ORCH001E Governed Autonomous Loop — see AS-ORCH-001E

## AS-ORCH-001B — Deterministic Policy Router + Typed TaskDirective

_Status: **IMPLEMENTED — READY FOR OWNER MERGE GATE** (independently verified 2026-08-28, see WORKLOG "ORCH001B-008"; `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md); not yet merged; not production-ready). Routes a 001A `OrchestrationDecision` to a typed `TaskDirective` or an explicit owner-gate / terminal result. Does **not** dispatch, create Cursor hooks, execute tasks, merge, or grant owner authority. `execution_authorized = false` always._

Honesty (mandatory):

- `STRUCTURED_RESULT_CONTRACT = IMPLEMENTED`
- `DETERMINISTIC_CLASSIFICATION = IMPLEMENTED`
- `DETERMINISTIC_POLICY_ROUTING = IMPLEMENTED`
- `TYPED_TASK_DIRECTIVE = IMPLEMENTED`
- `ROUTING POLICY IMPLEMENTED`
- `RUNTIME AUTOMATIC ROUTING NOT IMPLEMENTED`
- `CURSOR_HOOK = NOT_IMPLEMENTED`
- `AGENT_DISPATCH = NOT_IMPLEMENTED`
- `AUTONOMOUS_LOOP = NOT_IMPLEMENTED`
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`

Remediation role: existing taxonomy is `local` | `integration` | `autonomous`. There is no `implementation` role. `REMEDIATION_REQUIRED` targets `local` (least-authoritative existing role). Recertification remains `integration`.

- [x] ORCH001B-001 Typed `TaskDirective` + fail-closed `DirectivePermissions`
- [x] ORCH001B-002 Discriminated `OrchestrationRoute` (`task` | `owner_gate` | `terminal`)
- [x] ORCH001B-003 Deterministic policy table over 001A `NextTransition` values
- [x] ORCH001B-004 Source-result digest binding + decision/envelope consistency
- [x] ORCH001B-005 Read-only CLI `atlas orchestrator route-result`
- [x] ORCH001B-006 Shipped JSON schemas + model/schema parity tests
- [x] ORCH001B-007 Focused unit + composition + privilege-invariant tests
- [x] ORCH001B-008 Independent integration verification (2026-08-28: dedicated pass — dispatchable=true permission audit + decision/envelope consistency probe against `main` `718f2beb`, see WORKLOG "ORCH001B-008"; PASS)
- [x] ORCH001B-009 Owner-authorized activation: `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)
- [x] ORCH001C Cursor Integration — see AS-ORCH-001C (bridge + optional stop-hook adapter + explicit completion transport; authentic Cursor stop delivery ENVIRONMENT_DEPENDENT; dispatch NOT implemented)
- [x] ORCH001D Agent Dispatcher — see AS-ORCH-001D (fresh current-main single-hop; not #396)
- [x] ORCH001E Governed Autonomous Loop — see AS-ORCH-001E

## AS-ORCH-001C — Cursor Integration Bridge + Governed Stop Hook

_Status: **REMEDIATED — INDEPENDENTLY VERIFIED — READY FOR OWNER MERGE GATE** (AS-ORCH-001C-R1; re-certified 2026-08-28, see WORKLOG "ORCH001C-009"; ORCH001C-010 Local Windows explicit-completion acceptance = `PASS`, exercised 2026-08-28 end-to-end via the real CLI in a disposable directory (stage/complete/ack/idempotence/tamper-fail-closed all confirmed; zero dispatch, zero external calls, structurally guaranteed by `cursor_bridge.py`'s import graph) -- see WORKLOG "ORCH001C-010"; `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md); not yet merged; not production-ready). Surfaces a governed Atlas route via an optional Cursor stop-hook adapter **or** a deterministic explicit completion transport. Does **not** spawn agents, execute `TaskDirective`, merge, or grant authority. The stop hook is **not** the required primary runtime trigger._

Honesty (mandatory):

- `STRUCTURED_RESULT_CONTRACT = IMPLEMENTED`
- `DETERMINISTIC_CLASSIFICATION = IMPLEMENTED`
- `DETERMINISTIC_POLICY_ROUTING = IMPLEMENTED`
- `TYPED_TASK_DIRECTIVE = IMPLEMENTED`
- `CURSOR_BRIDGE_CORE = IMPLEMENTED`
- `CURSOR_STOP_HOOK_ADAPTER = IMPLEMENTED`
- `EXPLICIT_COMPLETION_TRANSPORT = IMPLEMENTED`
- `AUTHENTIC_CURSOR_STOP_EVENT_DELIVERY = NOT_RELIABLE_IN_CURRENT_WINDOWS_CLI_RUNTIME`
- `AUTHENTIC_CURSOR_STOP_EVENT_DELIVERY = ENVIRONMENT_DEPENDENT`
- `HOOK_RUNTIME_REQUIRED_FOR_CORE_FLOW = NO`
- `CROSS_AGENT_DISPATCH = NOT_IMPLEMENTED`
- `AGENT_DISPATCH = NOT_IMPLEMENTED`
- `AUTONOMOUS_LOOP = NOT_IMPLEMENTED`
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`

- [x] ORCH001C-001 Typed `CursorStopEvent` / `CursorBridgeState` / `CursorBridgeResponse`
- [x] ORCH001C-002 Single-slot runtime state under `.atlas/orchestration/cursor/` (gitignored)
- [x] ORCH001C-003 `atlas orchestrator cursor-stage-result` (recompute 001A+001B; fail closed on pending overwrite)
- [x] ORCH001C-004 Thin `.cursor/hooks.json` + `.cursor/hooks/atlas_stop.py` (no policy in the hook)
- [x] ORCH001C-005 One trusted `followup_message` for task/owner_gate; `{}` for terminal/aborted/error
- [x] ORCH001C-006 Loop guard + `atlas orchestrator cursor-ack` (ack != authority)
- [x] ORCH001C-007 Tamper/injection tests + hook stdin/stdout contract
- [x] ORCH001C-008 Read-only `atlas orchestrator cursor-status`
- [x] ORCH001C-R1-001 Typed `HandoffPacket` shared by hook adapter and explicit completion
- [x] ORCH001C-R1-002 `complete_staged_handoff` / `atlas orchestrator cursor-complete` (no Cursor event required)
- [x] ORCH001C-R1-003 Transport-equivalence + tamper + idempotence proofs
- [x] ORCH001C-009 Independent integration verification (re-certification required after R1 HEAD/TREE move) (2026-08-28: 44 existing tests re-run PASS + 10 black-box CLI probes -- 2 baseline + 8 adversarial, covering `cursor-status`/`cursor-stage-result`/`cursor-ack`/`cursor-complete` (the R1-added explicit-completion transport, initially missed -- added after review), including on-disk state-file tamper injection against both `cursor-status` and `cursor-complete` (`STAGED_STATE_TAMPERED`), transport-equivalence and idempotence evidence for `cursor-complete` -- against `main` `5ff62221`, see WORKLOG "ORCH001C-009"; PASS; still not merge-eligible)
- [x] ORCH001C-010 Local Windows explicit-completion acceptance (stop-event observation is non-blocking)
- [x] ORCH001C-011 Owner-authorized activation: `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)
- [x] ORCH001D Agent Dispatcher — see AS-ORCH-001D (fresh current-main single-hop; not #396)
- [x] ORCH001E Governed Autonomous Loop — see AS-ORCH-001E

## AS-ORCH-001D — Governed Single-Hop Agent Dispatcher (current-main reconstruction)

_Status: **IMPLEMENTED — READY FOR OWNER MERGE GATE** (ORCH001D-011 independently verified 2026-08-28 across two rounds -- round 1 found and remediated a real P2 (subprocess capture memory-bound) and, on independent re-verification, a real P1 (fix silently defeated the timeout when stdin was present); round 2 independently re-verified the fix clean with 7 further adversarial variants; see WORKLOG "ORCH001D-011"; ORCH001D-012 authentic-Cursor acceptance remains separately outstanding, `ATTEMPTED_BLOCKED_ON_ACCOUNT_USAGE_LIMIT` (2026-08-29, genuine attempt against the existing `docs/orch001c-010-cursor-acceptance-packet.md`, see D-206 including its own correction of an initially-missed packet and an over-count of authorized dispatches: first pair of dispatches hit `Workspace Trust Required`; owner then interactively trusted a dedicated `D:\atlas-cursor-acceptance` workspace (real `.workspace-trusted` marker independently confirmed, `trustedAt` matches); a separately-authorized third real dispatch against that now-trusted workspace passed the trust gate and reached Cursor's real cloud service, which returned a genuine account-level `ActionRequiredError: ... You're out of usage. Switch to Auto, or ask your admin to increase your limit` -- a real billing/usage-limit constraint on the owner's Cursor account, not an Atlas defect and not something this pass attempted to route around or retry against; no flag in `agent_transport.FORBIDDEN_CURSOR_FLAGS` (`-f`/`--force`/`--force-allow-http`) was used, and `--trust`/`--yolo` were never emitted -- not because they are forbidden-listed, but because they are simply outside the fixed flag allowlist the transport ever builds from) -- corrected 2026-08-28 from a false `EXTERNAL_BLOCKED` claim, see WORKLOG "Cursor CLI availability correction": a live Cursor CLI is genuinely present on this host; not merged; `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)). Starts exactly one target agent for a governed `HANDOFF_READY` dispatchable task, then stops. Does **not** auto-dispatch the next hop. Does **not** resurrect PR #396. Does **not** start AS-ORCH-001E._

Honesty (mandatory):

- `SINGLE_HOP_AGENT_DISPATCHER = IMPLEMENTED`
- `GENERAL_AGENT_DISPATCH_RUNTIME = IMPLEMENTED`
- `WINDOWS_CMD_WRAPPER_SUPPORTED = YES`
- `CURSOR_CLI_PROCESS_TRANSPORT = IMPLEMENTED`
- `MULTI_HOP_AUTODISPATCH = NOT_IMPLEMENTED`
- `AUTONOMOUS_LOOP = NOT_IMPLEMENTED`
- `DISPATCH_RECEIPT_IS_AUTHORITY = NO`
- `PR396_RESURRECTED = NO`
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`
- `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)

- [x] ORCH001D-001 Typed `DispatchRecord` / `DispatchReceipt` + shipped schemas
- [x] ORCH001D-002 Deterministic dispatch identity bound to trusted routing fields
- [x] ORCH001D-003 Single-active-dispatch slot under `.atlas/orchestration/dispatcher/`
- [x] ORCH001D-004 Eligibility revalidation (HANDOFF_READY + dispatchable + fail-closed privileges)
- [x] ORCH001D-005 Owner/terminal non-executing outcomes (`PROCESS_STARTED = NO`)
- [x] ORCH001D-006 Cursor CLI argv transport with Windows `.cmd` wrapper + stdin prompt
- [x] ORCH001D-007 `dispatch-submit-result` / `dispatch-recover` (no respawn)
- [x] ORCH001D-008 `atlas orchestrator dispatch-once` / `dispatch-status`
- [x] ORCH001D-009 Mutating remediation fail closed (`CAPABILITY_REQUIRED`)
- [x] ORCH001D-010 Focused unit + schema tests
- [x] ORCH001D-011 Independent verification (2026-08-28: round 1 IV found a real P2 -- capture bounded only on the returned value, not during collection -- remediated; round-1 *independent* re-verification found a further real P1 -- the fix silently defeated `timeout_seconds` whenever stdin was populated (always true on the real dispatch path) -- remediated; round-2 independent re-verification PASS with 7 further adversarial variants beyond round 1's, confirming the memory-bound fix stayed intact and no thread leak. 107 orchestration tests pass, ruff/mypy clean. See WORKLOG "ORCH001D-011"; still not merge-eligible)
- [ ] ORCH001D-012 Authentic Local Windows Cursor agent dispatch acceptance (unaffected by activation below -- separately outstanding; genuinely attempted 2026-08-29 through a real, owner-trusted workspace; transport/trust layers both proved correct end to end; blocked on the owner's Cursor account usage limit, an account/spend decision, not an Atlas defect -- see D-206)
- [x] ORCH001D-013 Owner-authorized activation: `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)
- [x] ORCH001E Governed Autonomous Loop — see AS-ORCH-001E

## AS-ORCH-001D-RESULT-BINDING-001 — process result capture / D-AS-ORCH-001D-RESULT-BINDING-014

_Status: **IMPLEMENTED — READY FOR OWNER MERGE GATE** (not merged; `MERGE_AUTHORIZATION = GRANTED`, 2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md). Extends the existing 001D parent so a terminal ask-mode process can return one framed `AgentResultEnvelope` that the parent validates and binds. Does **not** create a second dispatcher, grant ask-mode write, merge, or mutate PR #402/#396._

Honesty (mandatory):

- `PROCESS_DISPATCH_PATH_COUNT = 1`
- `DISPATCH_PATH = AS_ORCH_001D`
- `SECOND_PROCESS_LAUNCH_PATH = NO`
- `STDOUT_IS_AUTHORITY = NO`
- `STDERR_IS_AUTHORITY = NO`
- `PROCESS_EXIT_ZERO_IS_AUTHORITY = NO`
- `RESULT_ADAPTER_CAN_AUTHORIZE_MERGE = NO`
- `ASK_MODE_GENERAL_MUTATION = NO`
- `AS_ORCH_001A_R1 = BLOCKED` until a later owner merge of this package
- `PR402_CERTIFICATION = NOT_GRANTED`
- `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)

- [x] ORCH001DRB-001 Uniquely delimited terminal result frame
- [x] ORCH001DRB-002 Parent capture + 001A validation of untrusted payload
- [x] ORCH001DRB-003 Strict dispatch/lease/package/role/pin identity binding
- [x] ORCH001DRB-004 Replay fail-closed (duplicate/stale/wrong/after-finalization)
- [x] ORCH001DRB-005 Exit code is not semantic PASS
- [x] ORCH001DRB-006 Internal governed submit/finalize (child write not required)
- [x] ORCH001DRB-007 Independent verification (bootstrap: candidate tests + exact-head CI + Windows process matrix; adapter PASS is not self-trust; independently verified 2026-08-28, `PASS`, 32/32 tests + 15 adversarial frame-injection probes including real Windows CreateProcess -- see WORKLOG "EOD convergence wave")
- [x] ORCH001DRB-008 Owner-authorized activation: `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)

## AS-ORCH-001E — Governed Autonomous Loop

_Status: **IMPLEMENTED — READY FOR OWNER MERGE GATE** (ORCH001E-008 independently verified 2026-08-28, see WORKLOG "ORCH001E-008"; PASS with 3 non-blocking follow-ups recorded (2x P2 dead/misleading owner-gate guard + overstated AUTONOMY-001 honesty marker, 1x P3 crash-recovery liveness gap) -- no live authority leak found; not merged; `MERGE_AUTHORIZATION = GRANTED`, 2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md). Persistent loop above the landed 001D dispatcher. Does **not** bypass owner gates, authorize merge, grant waivers, expand objectives, or mutate #396._

Honesty (mandatory):

- `PERSISTENT_AUTONOMOUS_LOOP = IMPLEMENTED`
- `AUTONOMOUS_LOOP_001E = IMPLEMENTED`
- `SUCCESSOR_EXECUTION_UNDER_NEW_MODEL = ACTIVE`
- `LOOP_CAN_BYPASS_OWNER_GATE = NO`
- `LOOP_CAN_AUTHORIZE_MERGE = NO`
- `LOOP_CAN_GRANT_WAIVER = NO`
- `LOOP_CAN_EXPAND_OBJECTIVE = NO`
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`
- `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)

- [x] ORCH001E-001 Persisted loop state with fail-closed digest
- [x] ORCH001E-002 Tick: select READY → lease → 001D dispatch-once → stop
- [x] ORCH001E-003 Completion → validate → governor transition → DAG refresh
- [x] ORCH001E-004 Owner-gate and hard-blocker stop propagation
- [x] ORCH001E-005 Crash/restart recovery without duplicate dispatch
- [x] ORCH001E-006 Duplicate lease/result/dispatch prevention
- [x] ORCH001E-007 Adversarial matrix (authority, replay, corruption, cross-project)
- [x] ORCH001E-008 Independent verification (2026-08-28: 255 existing tests re-run PASS + 8 adversarial probes against `main` `0aa37abf`, ruff/mypy clean; PASS with 3 non-blocking follow-ups recorded, see WORKLOG "ORCH001E-008"; 2 of 3 follow-ups resolved as a side effect of ORCHAUT-010 (see below); the third, P3 crash-recovery orphaned-dispatch, tracked separately on PR #635, not yet certified)
- [x] ORCH001E-010 Owner-authorized activation: `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)
- [x] ORCH001E-011 `governor-loop-tick` CLI command had no node discovery/rehydration step -- constructed a brand-new empty `AutonomousGovernor` on every invocation (gap found during independent IV of PR #637, independently reproduced; see docs/evidence/D-204-GOVERNOR-LOOP-TICK-NO-NODE-REHYDRATION.md). Not fixed by PR #635 or PR #637 (both correct within their own tested scope; recovery failed earlier, on the empty governor's node lookup, before either fix's code was reached). Fixed here in `rehydration.py` — reuses the existing `AS-ORCH-DURABLE-LEASE-PROJECTION-001` lease projection plus `discover()`/`ingest_discovery()` (no second, competing persisted-DAG model); LEASED-phase recovery reconstructs the exact granted lease from durable evidence, fails closed (`NODE_NOT_REHYDRATABLE`) for any package_id other than the one deterministic node factory the governor has, and fails closed (`EXECUTION_STATE_NOT_REHYDRATABLE`) for DISPATCHING/AWAITING_RESULT/VALIDATING rather than guess at in-flight execution state. See D-205 for the authentic real-subprocess recovery proof (`test_real_subprocess_recovers_leased_pilot_node_after_crash`: two genuinely separate OS processes, independently re-run 2026-08-29, PASS) and the full adversarial matrix. **`GOVERNOR_LOOP_TICK_CLI_CROSS_PROCESS_RECOVERY` = `FUNCTIONAL` (demonstrated by the real-subprocess test above). `GOVERNOR_LOOP_TICK_CLI_CROSS_PROCESS_ORIGINATION` stays `NOT_FUNCTIONAL`/not yet demonstrated** -- the origination code path is fixed (originate-then-mark-ready), but the real `discover()` implementation has never returned an eligible non-pilot candidate yet (every hardcoded candidate is `eligible=False`, see `test_originate_marks_newly_discovered_node_ready`'s own docstring), so cross-process origination of genuinely new work is unproven, not merely unfixed.
- [x] ORCH001E-012 `_complete_validated()` dangling-`active_dispatch_id` stuck-loop gap (found during ORCH001E-011 independent IV, recorded but deliberately not fixed there -- see docs/evidence/D-205-ORCH001E-011-GOVERNOR-LOOP-REHYDRATION.md's "found, out of scope" section -- this line item itself was never actually added to this file at the time, a gap closed here alongside the fix). `apply_observed_result()` persists `phase=VALIDATING` well before its own final `_save(...)` clears `active_dispatch_id`; if whatever interrupted the call landed in that window, `_complete_validated()` used to see `active_dispatch_id is not None` and silently `return self._result()` forever -- no error, no state change, no progress. **Scope-narrowing, independently re-confirmed**: `rehydrate_governor()` (`rehydration.py`) already fails closed (`EXECUTION_STATE_NOT_REHYDRATABLE`) for `{DISPATCHING, AWAITING_RESULT, VALIDATING}` *before* `run_governor_loop_tick()` ever constructs an `AutonomousLoop` -- a real cross-process crash during VALIDATING was already safely rejected, not silently stuck; this gap is reachable only same-process (a caller retrying `tick()`/`recover()` on the same still-live `AutonomousLoop`/`AutonomousGovernor` objects after an interruption -- e.g. a future `run_until_stop()` caller or a hand-written retry -- `run_until_stop()` itself is not currently called by any production code path, only tests). Fixed in `loop.py` using the same established idiom PR #637 already applied to the LEASED/ACTIVE ambiguity: `_complete_validated()` now reads the governor's *current* node state (still live in-process) to learn how far the interrupted call actually got, then either safely redrives `apply_observed_result()` from scratch (node still LEASED/ACTIVE -- nothing was mutated yet, re-deriving `passed` from the dispatch port's own durable record via a new `_reobserve_dispatch_outcome()`, the same move `recover()` already makes for DISPATCHING/AWAITING_RESULT, rather than trusting a stale in-memory value never persisted anywhere) or finishes only the LoopState bookkeeping directly via a new `_finalize_validated()` helper (node already reached a terminal verified state -- CERTIFIED/OWNER_HELD/MERGE_ELIGIBLE, or BLOCKED, or REMEDIATING -- redriving would attempt an illegal transition out of an already-transitioned node). An unexpected node state (VERIFYING, or a passed/failed mismatch between the re-observed dispatch outcome and the node's own terminal state) fails closed with a new `VALIDATION_STATE_AMBIGUOUS` code rather than guessing. 7 new adversarial tests in `tests/unit/test_orchestration_autonomy_loop.py` (`test_validating_dangling_*`) construct the exact crash-window fixture and cover: IN_PROCESS redrive-to-completion, already-CERTIFIED bookkeeping-only finish (the illegal-transition hazard, directly proven not to raise), EXTERNAL dispatch re-observation (proven via an actually-invoked `recover()` call, not assumed), REMEDIATING resume, BLOCKED hard-stop, the ambiguous-VERIFYING fail-closed case, and an adversarial CERTIFIED-node-vs-FAILED-dispatch consistency mismatch fail-closed case; all 7 independently confirmed to fail against the pre-fix code and pass post-fix. No real cross-process/multi-process test was added for this specific gap -- per the scope-narrowing fact above it is not reachable cross-process at all (already-passing `test_orchestration_autonomy_rehydration.py`'s existing in-flight-phase matrix, including VALIDATING, re-run and still 20/20 PASS, unaffected by this change), so a subprocess test would not have exercised anything this fix changes. Full `orchestration or autonomy` suite: 334 passed (327 pre-existing + 7 new), 0 regressions. `ruff check .` and `mypy src`: clean (2 pre-existing, unrelated `connect_perf.py` `os.getrusage` Windows-stub errors, not touched here, matching D-205's own note).
- [ ] ORCH001E-009 Owner merge gate (not this package) -- activation of the stack is not a grant of automatic merge authority to the loop itself, which remains permanently Owner-reserved

## D-PHASE2A / AS-ORIGIN-001 — Specification-backed autonomous work origination

- [x] D-PHASE2A-1 Specification-backed work origination proof of concept: `src/project_atlas/orchestration/origination/` (facts, identity, adapter, proposal, policy, risk, materialize, projection, pipeline) derives governed `WorkNode`s only from evidence that already exists in a project's own repository (a fenced `docs/ROADMAP.md` record + a skip/xfail-marked spec test) -- `AI_INVENTED_WORK` is structurally unreachable, not merely discouraged by prompting. Additive-only extension of `orchestration/autonomy/rehydration.py` (new optional `origination_projection_store` parameter, `None` by default, byte-identical behavior for every existing caller) closes the sealed baseline's `CROSS_PROCESS_ORIGINATION = UNPROVEN` gap. Demonstrated end-to-end with 3 genuinely separate OS processes against the real Gamma/TASK-017 estate (origination+lease → real cross-process recovery → real `pytest` verification of a pre-existing implementation → completion → successor rescan correctly returning `NO_ELIGIBLE_WORK`); see `docs/adr/ADR-033-phase2a-specification-backed-work-origination.md` and `docs/evidence/d-phase2a/` (EVIDENCE.md, POC-RUNBOOK.md, receipts, demo script). **Explicit claim boundary** (do not overstate): `AUTONOMOUS_IMPLEMENTATION_EXECUTION = EXTERNAL/OWNER BLOCKED`, not proven -- no existing Atlas mechanism can autonomously write an implementation today (`governor.execute_leased()`'s only real IN_PROCESS call site records an evidence bundle, never a file write; the only real code-writing path, `EXTERNAL_AGENT`/Cursor, remains blocked on the owner's account usage limit, ORCH001D-012, unrelated to this package). 3 full rounds of independent adversarial IV (separate fresh agents each round, no self-certification), all CONFIRMED (round 1 and round 2 "with minor notes," round 3 unqualified CONFIRMED after every finding from both prior rounds was fixed and re-verified); 14/14 directive-required negative/adversarial matrix; exact-head CI PASS across all 4 gate jobs (control-plane, ubuntu 3.12 full, ubuntu 3.13 compat, windows) on the final merged commit. Also fixed, during automated-review remediation on the PR itself: a `RiskClassification` max_length that could be exceeded by the enum's own cardinality, an unguarded second file read, a path-traversal read primitive (evidence refs like `"../outside.py"` could read outside the intended project root -- fixed with an explicit, segment-based `".."` rejection; **the character-class-regex-alone insufficiency for embedded traversal segments like `"a/../b"` is an explicit, tested, load-bearing invariant, not incidental**), an origination-identity collision across multiple simultaneously-eligible roadmap items, discarded `WorkNode` dependency edges, and silently-erased declared blockers -- see `docs/evidence/d-phase2a/EVIDENCE.md`'s `AUTOMATED_REVIEW_REMEDIATIONS` section for the full account. Merged to `main` as PR #643 (merge commit `2cee1489`), 2026-08-30.
- [ ] D-PHASE2A-1a `orchestration.autonomy.governor.lease()`/`mark_ready()` do not themselves consult `WorkNode.dependencies` -- a proposal-level policy check in `origination/policy.py` (`UNSATISFIED_DEPENDENCIES`) is the only thing preventing a node with a real, unresolved dependency from being leased today, and that is caller-discipline, not a governed-DAG-layer chokepoint. Pre-existing property of `orchestration.autonomy`, not introduced by D-PHASE2A-1; tracked here as the gate that must close (or be otherwise mitigated) before origination is wired into any live autonomous dispatch loop. See `docs/evidence/d-phase2a/POC-RUNBOOK.md` "Known limitations".
- [ ] D-PHASE2A-2 Wiring origination into the live governed DAG/lease/dispatch loop (`orchestration/autonomy/loop.py` and friends) -- explicitly deferred by D-PHASE2A-1's own scoping ("Phase 2A-1 only... a separate later PR"), and additionally now gated behind an owner architecture decision: PR #642 (`feat/phase2a-specification-backed-origination`, still open as of this entry) is an independent, overlapping implementation of the same origination concept (`orchestration/origination.py`, single file) that has not been reconciled against the just-merged `orchestration/origination/` package. Do not begin D-PHASE2A-2 until the owner has chosen which origination implementation (or reconciliation of both) is authoritative -- wiring the wrong/superseded one into the live loop would be wasted, conflicting work. See the D-CODEX-ATLAS-PR643-POST-MERGE-SEAL-AND-GLOBAL-DAG-REOPEN final packet for the full reasoning.
- [ ] D-PHASE2A-3 No `atlas` CLI subcommand for origination yet -- reachable only via direct Python API calls (`originate_all`, `originate_new_only`, `materialize_work_node`) or the demo script (`docs/evidence/d-phase2a/run_three_process_demo.py`). Explicitly out of scope for D-PHASE2A-1 ("No CLI requirement for this wave"); a small, well-scoped follow-up (mirroring `run_governor_loop_tick`'s pattern), independent of the D-PHASE2A-2 architecture question.

## AS-ORCH-AUTONOMY-001 — Autonomous governor / operating-model transition

_Status: **IMPLEMENTED ON MAIN**. Formalizes a single logical autonomous governor, work DAG, leases, overlap gate, continuation, bounded remediation, IV routing, adversarial trigger, evidence hashing, and owner gates A–F. Process dispatch is owned by AS-ORCH-001D (this tree). Does **not** start AS-ORCH-001E, mutate #396, or merge._

Honesty (mandatory):

- `AUTONOMOUS_GOVERNOR = IMPLEMENTED`
- `WORK_DAG = IMPLEMENTED`
- `AGENT_LEASE_MODEL = IMPLEMENTED`
- `SURFACE_OVERLAP_GATE = IMPLEMENTED`
- `AUTONOMOUS_CONTINUATION_POLICY = IMPLEMENTED`
- `AUTOMATIC_REMEDIATION = IMPLEMENTED`
- `IV_ROUTING = IMPLEMENTED`
- `ADVERSARIAL_REVIEW_TRIGGER = IMPLEMENTED`
- `EVIDENCE_CONTRACT = IMPLEMENTED`
- `OWNER_GATES_A_F = IMPLEMENTED` (corrected back 2026-08-28 -- was PARTIALLY_IMPLEMENTED earlier the same day, found during ORCH001E-008 IV: gates C/D/E/F existed only as descriptive `OwnerGateKind` tags with zero `require_owner(...)` call sites. ORCHAUT-010 closed this: `governor.py::lease()` now enforces `require_owner(...)` for any owner_gate other than A, and `continuation.py::select_next` unconditionally excludes any owner-gated node from autonomous selection -- independently verified PASS in two rounds, merged as `7bcb8ea2`. See docs/evidence/D-200-ORCHAUT-010-GATE-CF-SELECT-LEASE-FIX.md and ORCHAUT-010 below.)
- `AGENT_DISPATCH = IMPLEMENTED_BY_AS_ORCH_001D`
- `MULTI_HOP_AUTODISPATCH = NOT_IMPLEMENTED`
- `AUTONOMOUS_LOOP_001E = IMPLEMENTED`
- `SUCCESSOR_EXECUTION_UNDER_NEW_MODEL = ACTIVE`
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`
- `MERGE_AUTHORIZATION = GRANTED` (2026-08-28, see docs/evidence/D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md)

- [x] ORCHAUT-001 Authoritative governor state + WHAT_CAN_RUN / WAIT / PARALLEL / OWNER
- [x] ORCHAUT-002 Work DAG with explicit recorded transitions
- [x] ORCHAUT-003 Surface overlap gate (unsafe parallel = NO)
- [x] ORCHAUT-004 Agent lease model; no autonomous scope expansion
- [x] ORCHAUT-005 Continuation policy; stop at owner gate / hard blocker
- [x] ORCHAUT-006 Bounded remediation (max 3) then BLOCKED
- [x] ORCHAUT-007 IV routing: implementer != verifier
- [x] ORCHAUT-008 Adversarial review trigger for control-plane / authorization
- [x] ORCHAUT-009 Deterministic hashed evidence bundles
- [x] ORCHAUT-010 Owner gates A–F fail closed -- reopened 2026-08-28 (found during ORCH001E-008 IV); fixed 2026-08-28 in two rounds (round 1: `continuation.py::select_next`/`loop.py::_select_and_lease` dead-code owner-gate check; round 2, found by independent IV: `governor.py::lease()`/`execute_leased()` reachable directly via `run_controlled_pilot()`/`continue_autonomous()`, bypassing the loop entirely) -- both rounds independently verified PASS by a separate agent. Merged as PR #633 / `7bcb8ea2`. See docs/evidence/D-200-ORCHAUT-010-GATE-CF-SELECT-LEASE-FIX.md.
- [x] ORCHAUT-011 CLI `governor-status` / `governor-discover` / `governor-pilot`
- [x] ORCHAUT-012 Controlled non-destructive in-process pilot
- [ ] ORCHAUT-013 Owner merge gate (not this package)

## AS-ORCH-AUTONOMY-001-PIN-RETARGET — trusted-anchor retarget / D-AUTONOMY-PIN-RETARGET-003

_Status: **IMPLEMENTED — READY FOR OWNER MERGE GATE** (not merged; merge authorization not granted). Replaces compile-time `EXPECTED_BASE_MAIN` as runtime authority with a provenance-bound trusted-anchor record. Initial retarget is the verified #398 merge (`62f8d59f...` / tree `aed48e48...`). Does **not** start R2/R6/R7/001E, mutate #396, or merge._

Honesty (mandatory):

- `STATIC_BOOTSTRAP_PIN_AS_RUNTIME_AUTHORITY = NO`
- `TRUSTED_ANCHOR_ADVANCEMENT = IMPLEMENTED`
- `GOVERNOR_CAN_INVENT_OWNER_AUTHORITY = NO`
- `GOVERNOR_CAN_ADVANCE_ANCHOR_FROM_OBSERVED_MAIN_ONLY = NO`
- `DESCENDANT_ONLY_IS_SUFFICIENT_AUTHORITY = NO`
- `UNVERIFIED_MAIN_MOVEMENT_FAILS_CLOSED = YES`
- `SUCCESSOR_EXECUTION_UNDER_NEW_MODEL = NOT_YET_ACTIVE`
- `AUTOMATIC_MERGE = NOT_IMPLEMENTED`
- `OWNER AUTHORITY = STILL REQUIRED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

- [x] ORCHAUT-014 Distinct BOOTSTRAP / TRUSTED_RUNTIME / OBSERVED pins
- [x] ORCHAUT-015 Shipped evidence-based #398 trusted-anchor record
- [x] ORCHAUT-016 Authorized advancement only when all §10 checks pass
- [x] ORCHAUT-017 Unauthorized / descendant-only / stale / concurrent / TOCTOU fail closed
- [x] ORCHAUT-018 Atomic compare-and-advance with append-only history
- [x] ORCHAUT-019 Negative matrix cases 1–15 + positive A/B/C
- [ ] ORCHAUT-020 Owner merge gate (not this package)

## AS-MDA-CONTROL-PLANE-COMPAT-001-R1 — mda-cli 0.2.9 control-plane compatibility

_Status: **RECONSTRUCTED — RECERTIFICATION IN PROGRESS** (owner-authorized because the previously certified Git object was lost before publication). Prior HEAD `4cb80a0aa0e28fbddee8c8a71f1875519f19fc92` remains historical evidence only. Prior certification is not transferable. This package does not touch PR #396 / AS-ORCH-001D._

- [x] MDA-R1-001 Explicit trusted 0.2.9 contract (`*.restructured.md`, `--out-dir`)
- [x] MDA-R1-002 Fail-closed missing / empty / stale / ambiguous / unknown-contract / confinement
- [x] MDA-R1-003 Focused reconstruction tests (18 cases) + mock models production contract
- [x] MDA-R1-004 Session-start-relevant stale `*.normalized.md` production refs = 0
- [ ] MDA-R1-005 Authentic PATH mda 0.2.9 + billed OpenRouter + `normalize_event` (host-blocked here)
- [ ] MDA-R1-006 Independent verification against published R1 HEAD/TREE
- [ ] MDA-R1-007 Exact-head GitHub CI + owner merge gate (merge not authorized)

## AS-ORCH-DURABLE-LEASE-PROJECTION-001 — durable read projection of governor leases

_Status: **IMPLEMENTING**. Projects primary-governor lease grant/release into a durable file for process-restart and subordinate read-only visibility. The projection is **not** authority. Grant/ack source remains the primary governor. Does **not** replace `AutonomousGovernor._leases`. Does **not** consume the Cursor bridge slot. Does **not** merge._

Honesty (mandatory):

- `PRIMARY_GOVERNOR_REMAINS_AUTHORITY = YES`
- `DURABLE_PROJECTION_IS_AUTHORITY = NO`
- `LEASE_GRANT_SOURCE = PRIMARY_GOVERNOR`
- `LEASE_ACK_SOURCE = PRIMARY_GOVERNOR`
- `CROSS_PROCESS_LEASE_VISIBILITY = PARTIAL_UNTIL_THIS_LANDS`
- `GLOBAL_AUTONOMY_BLOCKER = NO`

- [x] ORCHLEASE-001 Optional governor projection store (default off; existing tests unchanged)
- [x] ORCHLEASE-002 Atomic JSON projection + identity lock
- [x] ORCHLEASE-002a Exclusive nofollow tmp write (ORCH-LEASE-SYMLINK-ESCAPE-001)
- [x] ORCHLEASE-003 Reject stale / duplicate / foreign worker / foreign package / replay
- [x] ORCHLEASE-004 Ack + release visibility after process restart
- [x] ORCHLEASE-005 Focused + concurrent + control-plane tests
- [x] ORCHLEASE-006 Exact-head CI + independent IV + adversarial control-plane review (independently verified 2026-08-28, `PASS_WITH_NONBLOCKING_FINDINGS`, 127/127 broader autonomy suite, symlink-escape and tamper/replay defenses reconstructed adversarially, real concurrency race test -- see WORKLOG "EOD convergence wave")
- [ ] ORCHLEASE-007 Owner merge gate (not this package)

## Atlas 3.0 program (D-191 / D-192 / D-193)

_Status: **FOUNDATION CONVERGENCE — ISOLATED IMPLEMENTATION-READY**. Canonical
docs live under `docs/atlas-3/`. Runtime lives under `src/project_atlas/atlas3/`.
Does **not** rewrite certified 2.x demo surfaces. `FULL_LIVE_DEMO_READY = NO`.
`MERGE_AUTHORIZATION = NOT_GRANTED`. Chronicle remains ROADMAP_HORIZON.
Historical roadmaps are classified as inputs and are not erased._

- [x] AT3-DOC Program documents (north star, architecture, roadmap, epics, DAG, migration, UX, competitive, acceptance)
- [x] AT3-DOC-LLM D-192 LLM memory program documents
- [x] AT3-001 Foundation layer ownership (`FOUNDATION.md`)
- [x] AT3-002 Isolated project twin schema + constructors
- [x] AT3-010 Isolated repository/component inventory (declared; UNKNOWN if absent)
- [x] AT3-013 Isolated PR/commit/test/build nodes (ledger projection; no invented git)
- [x] AT3-011 Isolated file/symbol graph (declared; no host walk)
- [x] AT3-012 Isolated service/environment nodes (declared fixture; not authentic estate)
- [x] AT3-003 Isolated engineering event model (canonical envelope)
- [x] AT3-004 Isolated semantic capability registry
- [x] AT3-005 Isolated 2.x→3.x compatibility prover
- [x] AT3-006 Foundation threat catalog (reviewed; not certified)
- [x] AT3-014 Isolated universal event ledger
- [x] AT3-015 Isolated Atlas Pulse (eight questions)
- [x] AT3-030 Isolated Atlas Start (budget + freshness)
- [x] AT3-050 Isolated AGENT_PROOF
- [x] AT3-035/036/039/040/041/042/044/047/048/049 Isolated ChatGPT-first memory vertical
- [x] AT3-036 Isolated ChatGPT export ingest (parse_chat_export compose; live history claim fails closed; does not replace chatgpt_bridge)
- [x] AT3-039 Isolated conversation normalization (canonical envelope; mixed corrupt fail-closed; no new CLI)
- [x] AT3-040 Isolated conversation extractor (landed ITEM_TYPES; forged owner stays proposed; no Truth Core)
- [x] AT3-041 Isolated cross-LLM dedup (provenance retained; no state/intent/history collapse)
- [x] AT3-042 Isolated cross-LLM conflict detection (no winner; no layer collapse)
- [x] AT3-044 Isolated memory freshness (STALE != CURRENT; UNKNOWN stays UNKNOWN)
- [x] AT3-047 Isolated privacy/secret gate (fail-closed scan; raw transcript minimized)
- [x] AT3-048 Isolated unified memory search (extracted items only; not a transcript dump)
- [x] AT3-049 Isolated memory reconciliation (compose 041/042/044; never auto-promote)
- [x] AT3-CHRONICLE Horizon design notes only (no runtime)
- [x] AT3-037 Isolated Claude fixture/export ingest (native history sync remains NOT IMPLEMENTED)
- [ ] AT3-037 Claude native history sync (NOT IMPLEMENTED; EXPORT_ONLY honesty)
- [x] AT3-038 Isolated Gemini fixture/export ingest (native history sync remains NOT IMPLEMENTED)
- [ ] AT3-038 Gemini native history sync (NOT IMPLEMENTED; EXPORT_ONLY honesty)
- [x] AT3-043 Isolated conversation decision + intent extraction
- [x] AT3-045 Isolated provider session lineage
- [x] AT3-061 Isolated intent vs current-state honesty wrapper
- [x] AT3-060 Isolated causal graph (declared CAUSED_BY; graph != authority)
- [x] AT3-062 Isolated DECIDED_BY provenance (owner_origin required)
- [x] AT3-020 Isolated claim/decision/requirement nodes (declared; graph != authority; no Truth Core write)
- [x] AT3-021 Isolated derived relationship expansion (GRAPH_REUSE aliases; no AS-GRAPH-003 write)
- [x] AT3-022 Isolated conflict/UNKNOWN projection (UNKNOWN stays UNKNOWN; no winner; no healthy filter)
- [x] AT3-023 Isolated graph != authority prover (winners/trust fail closed; no AS-GRAPH-003 write)
- [x] AT3-051 Isolated independent-verification binding (exact HEAD/TREE; IV != MERGE)
- [x] AT3-052 Isolated ADV binding (exact HEAD/TREE; ADV != MERGE / != security cert)
- [x] AT3-070 Isolated surface contract (CLI/API/Web/TUI/MCP/A2A; surface != authority)
- [x] AT3-071 Isolated transport != authority prover (HTTP/CLI/MCP/A2A success != authority)
- [x] AT3-072 Isolated provider-register / capabilities CLI design (no CLI proliferation)
- [x] AT3-080 Isolated impact explorer data (declared; graph != authority; no trust scores)
- [x] AT3-100 Isolated twin health (derived signals; health != authority; estate != authorization)
- [x] AT3-090 Isolated Atlas Home composer (Pulse+Start+twin health; UI != truth)
- [x] AT3-091 Isolated Timeline (declared valid-time; wall-clock != valid-time)
- [x] AT3-094 Isolated Decision Explorer (declared owner_origin; model paraphrase != owner)
- [x] AT3-092 Isolated Truth Graph UX (declared claims/relationships; graph != authority)
- [x] AT3-096 Isolated Mission Command Center (declared DAG/leases; no self-merge)
- [x] AT3-095 Isolated Impact Explorer UX (composes AT3-080; no new CLI)
- [x] AT3-110 Isolated multi-project twin (declared siblings; federation != authority)
- [x] AT3-111 Isolated org identity (declared only; does not mint)
- [x] AT3-081 Isolated stale/conflict intelligence (Pulse + memory compose; no winner; stale != current)
- [x] AT3-082 Isolated next-action honesty (Pulse + next-lens compose; NEXT != command; no write)
- [x] AT3-093 Isolated Time Machine UX reuse (kdiff only; no second clock; wall-clock != valid-time)
- [x] AT3-112 Isolated federation reuse honesty (FED-001/002 compose; federation != authority; no promote)
- [x] AT3-053 Isolated autonomy gate reuse (orch DAG/lease compose; no self-dispatch; lease != merge)
- [x] AT3-101 Isolated ledger observability (validated read; ledger != truth; no healthy filter)
- [x] AT3-102 Isolated provider sync status (honest capabilities; AT3-046 EXTERNAL_BLOCKED)
- [x] AT3-046 Isolated incremental export-cursor (local apply only; live provider incremental EXTERNAL_BLOCKED)
- [x] AT3-054 Isolated consume-only memory context compiler (no 2.x rewrite; stale != current; UNKNOWN stays UNKNOWN)
- [x] AT3-055 Isolated ranked-context local serve (chatgpt/claude/gemini/cursor pack; live serve EXTERNAL_BLOCKED)
- [x] AT3-056 Isolated fixture provider handoff (ChatGPT→Claude fixture path; live multi-account EXTERNAL_BLOCKED)
- [x] AT3-057 Isolated Cursor fixture / local-session ingest (AGENTS.md != ingestion; Cursor Cloud history NOT IMPLEMENTED)
- [ ] AT3-057 Cursor Cloud history sync (NOT IMPLEMENTED; LOCAL_SESSION honesty)
- [x] AT3-058 Isolated Codex fixture / structured-submission ingest (CODEX.md != ingestion; native history NOT IMPLEMENTED)
- [ ] AT3-058 Codex native history sync (NOT IMPLEMENTED; STRUCTURED_SUBMISSION honesty)
- [ ] AT3-046 Incremental live provider sync (EXTERNAL_BLOCKED; credentials / history API)
- [ ] Chronicle / Ambient Knowledge runtime (ROADMAP_HORIZON)
- [ ] AT3-003/014 certified-surface implementation after `FULL_LIVE_DEMO_READY = YES`

