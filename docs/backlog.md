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

- [ ] C-001 Recursive source scanner
- [ ] C-002 Include/exclude configuration
- [ ] C-003 MIME and extension detection
- [ ] C-004 Streaming SHA-256 hashing
- [ ] C-005 Exact duplicate grouping
- [ ] C-006 Manifest persistence
- [ ] C-007 Unsupported file reporting
- [ ] C-008 Path traversal tests

## Epic D — Parsing

- [ ] D-001 Markdown parser
- [ ] D-002 YAML frontmatter parser
- [ ] D-003 Plain-text parser
- [ ] D-004 Heading extraction
- [ ] D-005 Link extraction
- [ ] D-006 Parser registry
- [ ] D-007 Malformed input tests

## Epic E — Classification

- [ ] E-001 Explicit override rules
- [ ] E-002 Path rules
- [ ] E-003 Filename rules
- [ ] E-004 Frontmatter rules
- [ ] E-005 Heading rules
- [ ] E-006 Classification method audit field
- [ ] E-007 Unknown classification path

## Epic F — Generation

- [ ] F-001 Stable ID strategy
- [ ] F-002 Frontmatter renderer
- [ ] F-003 Project note renderer
- [ ] F-004 Source reference renderer
- [ ] F-005 Conflict renderer
- [ ] F-006 Deterministic ordering
- [ ] F-007 Atomic file writes

## Epic G — Human-safe updates

- [ ] G-001 Protected marker parser
- [ ] G-002 Generated-region replacement
- [ ] G-003 Human-region preservation
- [ ] G-004 Fail-closed malformed marker handling
- [ ] G-005 Golden-file tests

## Epic H — Validation

- [ ] H-001 YAML validator
- [ ] H-002 Schema validator
- [ ] H-003 Link validator
- [ ] H-004 Provenance validator
- [ ] H-005 Lifecycle validator
- [ ] H-006 Freshness validator
- [ ] H-007 Orphan validator
- [ ] H-008 Secret scanner
- [ ] H-009 Coverage validator
- [ ] H-010 Severity exit codes

## Epic I — Portfolio intelligence

- [ ] I-001 Project index generator
- [ ] I-002 Portfolio overview
- [ ] I-003 Maturity matrix
- [ ] I-004 Documentation gap report
- [ ] I-005 Stale knowledge report
- [ ] I-006 Conflict review queue
- [ ] I-007 Dependency report
- [ ] I-008 Capability report

## Epic J — Incremental operation

- [ ] J-001 State cache
- [ ] J-002 Added source detection
- [ ] J-003 Changed source detection
- [ ] J-004 Removed source handling
- [ ] J-005 Impact graph
- [ ] J-006 Selective regeneration

## Epic K — Pilot onboarding

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
- [ ] CORE-SEC-001 Implement content-based secret detection and redaction for
  pilot ingestion. Filename-only sensitive-file detection must not be treated
  as sufficient for real-project ingestion.
