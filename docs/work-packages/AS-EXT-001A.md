# AS-EXT-001A — Structured Evidence Parsers, Locator Refinement, and Compilation-Status Reporting

## Package identity

- **Package:** AS-EXT-001A
- **Title:** Structured Evidence Parsers, Locator Refinement, and Compilation-Status Reporting
- **Directive:** D-PROJECT-ATLAS-KIMI-AS-EXT-001A-001
- **Parent directive:** D-PROJECT-ATLAS-KIMI-SWARM-PARALLEL-INTAKE-001
- **Base commit:** `6d874751d3ed9cb05433a8d50ab372a997418d84` (merged PR #5)
- **Branch:** `feat/as-ext-001a-structured-evidence`
- **Implementation worktree:** `D:\atlas-worktrees\atlas-as-ext-001a` (single writing owner)
- **Primary evidence:** EXP-ATLAS-SELFHOST-BASELINE-001 at
  `D:\atlas-selfhost\baseline-6d87475\` (`P0-SYNTHESIS-REPORT.md`,
  `BASELINE-RESULT.md`, `FIXTURE-CURATION-P0-C.md`)
- **Final merge:** Project Owner authorization required. Production deployment: not authorized.

## Measured failure addressed

Official P0 self-host baseline (EXP-ATLAS-SELFHOST-BASELINE-001, target
`6d874751d3ed9cb05433a8d50ab372a997418d84`):

- Corpus: 70 files / 14,269 lines / 641,925 bytes.
- Batch `atlas ingest` aborts closed at the LOCATOR stage on the first failing
  source (`docs/evidence/AS-CORE-002-post-merge-receipt.yaml`,
  `class=validation`, line `status: certified`): 0 claims for the whole corpus.
- Per-file isolated ingest: 39 success / 31 failure — 29
  `locator_normalization_failed` (structured YAML evidence) + 2
  `ambiguous_identity_boundary` (`VERIFY-AS-RET-SEQUENCING-DECISION.md`,
  `docs/plan.md`).
- Verified canonical claim count: 15 (canonical `claims.json.ids`).
- Explicit `{#id}` anchors in the corpus: 0, so "Explicit ID required" is
  unsatisfiable for the failing sources today.
- Claim yield: approximately 1.05 claims per 1,000 lines.

### Root cause (verified against executable behavior)

1. **29 locator failures.** `project_atlas.claim_identity.resolve_locator`
   recognizes only explicit `{#id}` anchors, a compiler `schema_key`, the
   project-manifest marker, or the *nearest Markdown heading*. Flat evidence
   YAML files contain none of these. Their `status:`-style lines match the
   shared line rules, extraction runs with `reject_unresolved=True`, and
   `UnresolvedLocatorError` is re-raised by `knowledge_compiler._extract` as
   `Locator normalization failed: No stable locator found. Explicit ID
   required.` Ingestion fails closed, so one bad file aborts the whole batch.
2. **2 collisions.** The heading locator records only the slug of the nearest
   heading — no ancestor path, no subject, no block/structural scoping. In the
   VERIFY document, three sibling `status:` lines under one title heading, and
   in `docs/plan.md` two identical foreign H1s (`# Nebula Control Platform`,
   lines 301 and 803), produce identical v2 identity tuples
   `(project, source, claim_type, field, locator)`. `compile_knowledge`
   detects the duplicate claim id and raises `ambiguous identity boundary`
   (fail closed, by design).

## Scope (directive §7)

1. **7.1 Source classification correction** — deterministic, specific-first
   precedence: explicit recognized schema/type marker → known evidence
   path/profile → ADR path/title profile → work-package path/profile →
   backlog/roadmap/WORKLOG path → dedicated YAML/YML source → registered
   structured YAML-in-Markdown profile → generic Markdown → unsupported/other.
   Content keywords such as `architecture` and `design` must not override a
   more specific structural classification. Classification records
   `source_kind`, `document_profile`, `classification_rule`,
   `classification_confidence`, and parser selection.
2. **7.2 Parser output contract** — one immutable, validated parser-output
   model with (at minimum) `parser_id`, `parser_version`, `source_kind`,
   `document_profile`, `claim_type`, `subject`, `normalized_field`,
   `raw_value`, `normalized_value`, `stable_semantic_locator`, `locator_kind`,
   `locator_confidence`, `source_path`, `source_span`, `structural_context`,
   `authority_hint`, `ambiguity_status`. Parser output never calculates final
   claim identity; Claim Identity v2 remains the sole identity contract.
3. **7.3 Static parser dispatch** — small static path/signature dispatch with
   file-level parser exclusivity: compatibility key-value extraction, evidence
   YAML, dedicated YAML/YML structured sources, registered VERIFY structured
   document profile, ADR only where justified by the corpus and acceptance
   tests. No plugin framework, no interval tree, no unrestricted mixed-region
   parsing.
4. **7.4 YAML path locators** — canonical `yamlpath:<dotted.path>` semantic
   locators with Unicode NFC normalization, deterministic output, independence
   from indentation/formatting/mapping order, no values/line numbers/absolute
   paths in locators, safe reserved-character handling, Claim Identity v2
   tuple compatibility, stable keys for sequence items (numeric indexes
   provisional only), and an explicit diagnostic for duplicate keys.
5. **7.5 Evidence receipt profiles** — common semantic concept mapping +
   profile-specific adapters + unknown structured field preservation. Fields
   classified as USER-FACING CLAIM / PROVENANCE METADATA / EVIDENCE METADATA /
   UNKNOWN STRUCTURED METADATA / DIAGNOSTIC ONLY. Unknown fields remain
   visible. No receipt ever falls back to generic Markdown or line-regex
   parsing. Every receipt receives recognized / partially-recognized /
   unknown-profile / invalid status. An unknown-profile receipt still
   contributes canonical claims extracted from recognized root keys: those
   candidates compile as COMPLETE_CANDIDATE and promote normally, accompanied
   by an `unknown-receipt-profile` warning diagnostic; only unrecognized
   fields are preserved as UNKNOWN STRUCTURED METADATA.
6. **7.6 VERIFY structured profile** — registered structural profile producing
   distinct subjects and locators for `status`, `decision`,
   `verify_disposition.status`, `as_ret_disposition.status`, with zero
   collision, zero false semantic conflict, zero whole-run abort.
7. **7.7 Heading-locator collision remediation** — root-cause and fix both
   official collision fixtures with the smallest stable resolution (full
   heading path, subject, normalized field/label, structural key where
   available). Where no safe locator exists: withhold the claim, produce a
   diagnostic, mark the candidate PARTIAL, do not abort independent
   extraction, do not promote canonically.
8. **7.8 Compilation outcomes** — state machine
   `START → DISCOVERING → EXTRACTING → VALIDATING_CANDIDATE →
   COMPLETE_CANDIDATE / PARTIAL_CANDIDATE / FAILED → PROMOTING (only from
   COMPLETE_CANDIDATE) → COMPLETE or PROMOTION_FAILED`. PARTIAL_CANDIDATE is
   staging/candidate only: diagnostics + counters, no canonical state change,
   no lifecycle promotion, never reported as complete.
9. **7.9 Diagnostic model** — structured diagnostics for unresolved locator,
   duplicate locator, ambiguous identity, duplicate YAML key, unknown receipt
   profile, unknown structured field, invalid receipt, unsupported source
   kind, classification ambiguity, parser failure, alias ambiguity, promotion
   failure. Each carries code, severity, source path, source span where known,
   parser, profile, subject, field, locator, reason, remediation, continued,
   canonical impact. No silent drop.
10. **7.10 Locator refinement and aliases** — identity algorithm stays v2;
    parser version is parser-specific; locator-strategy version tracked
    explicitly if required. Migrations classified ONE→ONE (automatic alias
    candidate), ONE→MANY (ambiguity record, no automatic promotion),
    MANY→ONE (semantic collapse review), MANY→MANY (manual/profile-specific),
    NO STABLE OLD LOCATOR (new identity with explicit historical
    discontinuity). The existing merged v2 alias mechanism
    (`project_atlas/migrations/claim_v2_migration.py`, `claim-alias` schema)
    is reused; no parallel migration subsystem.

## Out of scope (directive §11)

Unrestricted prose extraction; generic NLP; LLM extraction; Markdown task
parser; Markdown table parser; generic front-matter parser unless required by
a MUST fixture; interval tree; full parser plugin ecosystem; retrieval CLI;
freshness validation; impact graph; broad authority-engine redesign; broad
conflict-engine redesign; ingestion decomposition; Claim Identity v3; partial
canonical promotion; governance-system expansion; sibling control-plane work.

## Design decisions and rationale

Frozen by P0 synthesis; recorded here so they are not relitigated.

- **Parser output model: frozen Pydantic v2.** Pydantic v2 is the existing
  project convention (`project_atlas.domain`, strict mypy, `ConfigDict`
  models). It provides the boundary validation this package exists for,
  produces high-quality structured diagnostics on invalid input, and generates
  JSON schemas for free through the existing
  `project_atlas.schema`/`src/project_atlas/schemas/` convention. Real output
  volumes are corpus-scale (15 claims today; hundreds–low-thousands of parser
  records even at full success), so the 100,000-object micro-benchmark cited
  in prototype evidence is not decision-grade and was not the basis. An
  immutable dataclass model would add a second modeling convention with no
  measured benefit and weaker maintainability.
- **Dispatch: static path/signature, file-level parser exclusivity.** All P0
  failures are whole-file-class failures; no measured mixed document needs
  multiple parsers within one file. No interval tree, no plugin framework.
- **YAML: safe loading only.** No arbitrary object construction; profile-schema
  false-positive control (a YAML candidate must parse to a mapping AND satisfy
  a known profile schema); no unrestricted `yaml.safe_load` over arbitrary
  Markdown; no generic line-regex fallback for receipts.
- **PARTIAL outcomes: candidate/staging only.** PARTIAL_CANDIDATE never alters
  canonical state and never triggers lifecycle promotion. Canonical promotion
  atomicity is unchanged — the merged ingestion/OCC compare-and-swap contract
  with per-project atomic promotion and tested rollback (AS-CORE-003,
  CORE3-023) remains authoritative.
- **Identity: Claim Identity v2 unchanged.** Parser-derived locator changes
  are LOCATOR REFINEMENT, not Claim Identity v3. Aliases are created via the
  existing v2 alias mechanism only for provable one-to-one mappings;
  unprovable mappings remain unpromoted.

## Security bounds policy (directive §8)

Implemented and tested, enforced (not merely documented), with configurable
bounded defaults. Initial defaults and rationale are recorded with actual
corpus measurements during the security-bounds commit:

- safe YAML loading only; no arbitrary object construction;
- duplicate-key rejection with explicit diagnostic;
- bounded nesting depth, bounded alias expansion (alias amplification), bounded
  total node count, bounded file size, bounded scalar and sequence sizes where
  practical;
- malformed encoding diagnostics; control-character handling; Unicode NFC
  normalization;
- path normalization and traversal protection (existing AT-013 contract);
- rejected inputs are never silently skipped — each yields a structured
  diagnostic.

## Acceptance criteria (directive §10 MUST, §13)

MUST:

- all 31 real receipts structurally parse without unhandled exceptions;
- every receipt obtains a support/profile status;
- evidence files are not classified as architecture solely due to content keywords;
- flat YAML obtains stable locators; nested YAML obtains stable locators;
- VERIFY yields distinct claims and no collision;
- both collision fixtures no longer abort;
- duplicate keys fail explicitly;
- one bad source does not prevent extraction from independent good sources;
- PARTIAL candidate never alters canonical state;
- COMPLETE candidate alone may promote; promotion failure rolls back;
- diagnostics reconcile with withheld sources and claims;
- deterministic repeat produces byte-identical candidate output;
- Claim Identity v2 tests remain green; compiler and migration remain consistent;
- aliases only promoted for provable one-to-one mappings; one-to-many mappings
  remain ambiguous;
- source/parser provenance exists on every emitted claim;
- claim counts come from canonical JSON/index structures and are independently
  cross-checked.

SHOULD: ADR profile support; malformed receipt recovery; resource-limit
diagnostics; Unicode and reserved-character properties; unsupported-source
inventory; zero-write unchanged replay.

Product target (§13): LEVEL 0 — the full RAW 70-file corpus completes without
an unhandled abort. Progress toward Level 1: every emitted claim traceable,
every unsupported/withheld item visible, classification and parser provenance
recorded, partial status visible, canonical state protected. Conflict
preservation against real data may remain NOT YET EXERCISED and must not be
falsely reported as validated.

## Product metrics baseline (directive §12)

Before: 70 files / 14,269 lines / 641,925 bytes; 39 independently successful;
31 failed; 15 verified claims; whole-batch abort; ≈1.05 claims per 1,000
lines. After-values are recorded with the self-host evidence commit; rising
claim count alone is not evidence of usefulness.

After (EXP-ATLAS-SELFHOST-AS-EXT-001A-001, receipt
`docs/evidence/AS-EXT-001A-level0-selfhost-receipt.yaml`): 70 files /
14,269 lines / 641,925 bytes; full pipeline exit 0 end-to-end (≈9.5 s);
65 sources compiled — 64 COMPLETE_CANDIDATE, 1 PARTIAL_CANDIDATE
(`docs/prp.md`, 1 withheld architecture-fallback claim, staging-only),
0 FAILED — plus 5 pre-existing security quarantines (70 accounted);
91 canonical claims cross-checked between canonical state and the generated
claims index (91 == 91); 1 claim withheld; 35 diagnostics; 5 conflicts
preserved; 6.38 claims per 1,000 lines; deterministic repeat byte-identical
(two independent vaults, 132 files) and zero-mutation settled replay.

Remediation (adversarial review, receipt
`docs/evidence/AS-EXT-001A-level0-selfhost-receipt-v2.yaml`, commit 33bc65a):
the experiment was re-run after fixing one blocking executable violation
(intra-source yamlpath locator collisions escaping per-source isolation) and
five concerns. Every §12 after-value above reconciles exactly on the
remediated re-run (64 COMPLETE / 1 PARTIAL / 0 FAILED + 5 quarantined; 91
claims; 35 diagnostics; 5 conflicts; 6.38 claims per 1,000 lines; two vaults
byte-identical; settled replay byte-stable). Wording corrections recorded in
the V2 receipt: quarantine accounting is 6 injection findings across 4 files
plus 1 secret finding in 1 file (= 5 quarantined files), and settled replay
means the first replay mutates via lifecycle re-observation while the third
and subsequent ingests are byte-stable. All 65 compilation outcomes now also
persist their classification records.

## Hard escalation conditions (directive §21)

Stop and report BLOCKED if: safe implementation requires changing Claim
Identity v2; existing alias infrastructure cannot represent a required
migration safely; canonical atomicity cannot support staging
non-destructively; repository permissions block branch/PR creation; a security
limit has two materially incompatible product choices; official fixtures
contradict the package premise; the full RAW corpus remains below Level 0
after two bounded remediation iterations; repository corruption or data-loss
risk appears; production deployment is proposed; or the final PR is
merge-ready.

## Commit plan (directive §14)

1. package contract and frozen fixtures;
2. compilation outcome model;
3. parser-output model;
4. classification precedence;
5. YAML parsing and locators;
6. evidence profiles;
7. VERIFY profile;
8. heading-locator remediation;
9. diagnostics;
10. alias handling;
11. security bounds;
12. self-host evidence and documentation.
