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
- [ ] D-006 Parser registry
- [x] D-007 Malformed input tests

## Epic E — Classification

- [x] E-001 Explicit override rules
- [x] E-002 Path rules
- [x] E-003 Filename rules
- [x] E-004 Frontmatter rules
- [x] E-005 Heading rules
- [ ] E-006 Classification method audit field
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
- [ ] H-006 Freshness validator
- [ ] H-007 Orphan validator
- [x] H-008 Secret scanner
- [x] H-009 Coverage validator
- [ ] H-010 Severity exit codes

## Epic I — Portfolio intelligence

_Remaining items (I-002 through I-005, I-007, I-008) are scoped under
**AS-MVP-001** (architecture entry passed; see
`docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md`). Not
marked complete until implemented and independently verified._

- [x] I-001 Project index generator
- [ ] I-002 Portfolio overview
- [ ] I-003 Maturity matrix
- [ ] I-004 Documentation gap report
- [ ] I-005 Stale knowledge report
- [x] I-006 Conflict review queue
- [ ] I-007 Dependency report
- [ ] I-008 Capability report

## Epic J — Incremental operation

- [x] J-001 State cache
- [x] J-002 Added source detection
- [x] J-003 Changed source detection
- [x] J-004 Removed source handling
- [ ] J-005 Impact graph
- [x] J-006 Selective regeneration

## Epic K — Pilot onboarding

_All items are scoped under **AS-MVP-001** (architecture entry passed;
see `docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md`).
Not marked complete until implemented and independently verified._

- [ ] K-001 Nebula fixture corpus
- [ ] K-002 Black Agency OS fixture corpus
- [ ] K-003 Dark Factory fixture corpus
- [ ] K-004 Expected manifests
- [ ] K-005 Expected generated vault
- [ ] K-006 Contradiction fixtures
- [ ] K-007 Secret fixtures

## Cross-cutting follow-up — Atlas Core vertical slice

- [ ] CORE-MODEL-001 Integrate `ConceptRecord`, `Claim`, and
  `ProvenanceReference` into formal project projections and richer validated
  project frontmatter; the current slice intentionally uses a thin
  `SourceRecord`-backed projection.
- [ ] CORE-OPS-001 Add explicit read-before-write/hash-before-replace
  accounting and evidence for filesystem-write suppression on unchanged
  replay. Keep `content drift` and `canonical content changes` distinct from
  physical filesystem writes.
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
- [ ] INT-009 Define raw-package and receipt retention policy
- [ ] INT-010 Preserve removed-package/deletion state in projections
- [ ] INT-011 Define receipt revocation and invalidation semantics
- [ ] INT-012 Define schema migration and compatibility tooling
- [ ] INT-013 Run the bounded multi-project integration pilot

## AS-CORE-002 — Semantic domain model and source lifecycle hardening

- [x] CORE2-001 Add strict versioned Project, source lifecycle, authority,
  coverage, validation, decision, work-package and agent-event reference models
- [x] CORE2-002 Add semantic record schema and schema validation coverage
- [x] CORE2-003 Compile deterministic rich project metadata and coverage
- [x] CORE2-004 Preserve human regions and fail closed on malformed markers
- [x] CORE2-005 Add content-based secret findings with metadata-only output
- [x] CORE2-006 Persist source lifecycle state and deletion tombstones
- [ ] CORE2-007 Complete ConceptRecord/Claim projection composition and migrations
- [ ] CORE2-008 Add duplicate-source conflict projections and authority review queue
- [ ] CORE2-009 Add interrupted-write recovery and complete write accounting
- [ ] CORE2-010 Run controlled pilot lifecycle certification

## AS-ID-001 — Durable Source Lineage Identity

- [x] ID-001 Add UUIDv4 project genesis with injected test providers
- [x] ID-002 Add Core-local project identity synchronization
- [x] ID-003 Add source registry v2 and durable lineage derivation
- [x] ID-004 Add canonical path and raw-byte fingerprint contracts
- [x] ID-005 Add atomic v1-to-v2 migration receipts
- [x] ID-006 Add duplicate-identity and ambiguity fail-closed checks
- [x] ID-007 Add replay, rollback, concurrency, and schema validation tests
- [x] ID-008 Governor review and independent certification
