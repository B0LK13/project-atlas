# ADR-005 — MVP portfolio intelligence and pilot onboarding closure

**Status:** accepted for implementation
**Date:** 2026-08-03
**Work package:** AS-MVP-001
**Author:** Architecture Governor (entry-gate authorization)

## Context

`docs/prp.md` §7 defines the MVP boundary as including "three pilot
fixtures" and §8's success metrics require "all pilot projects produce a
project overview, source index, gap report, and status confidence state."
`docs/master-roadmap.md` states plainly that "Atlas Core is not yet an
MVP." Checking the live backlog (`docs/backlog.md`) against the actual
repository:

**Epic I — Portfolio intelligence (2 of 8 complete):**

| Item | Status | Evidence |
|---|---|---|
| I-001 Project index generator | **complete** | `build_indexes()` in `src/project_atlas/indexes.py` writes `generated/navigation/projects.md` and `generated/navigation/portfolio.md`, a flat list of project links |
| I-002 Portfolio overview | not implemented | no portfolio-wide aggregation exists; only a flat project-link list |
| I-003 Maturity matrix | not implemented | `Maturity` (`src/project_atlas/domain/vocabulary.py`) is a defined per-concept enum (concept/prototype/mvp/beta/production-candidate/production/hardened) used by `ConceptRecord.maturity`, but nothing aggregates it across projects |
| I-004 Documentation gap report | not implemented | `coverage_for()` (`src/project_atlas/semantic_compiler.py`) already computes **per-project** `CoverageRecord`s (category, state: absent/partial/present/stale/conflicting, source_ids) against a fixed `COVERAGE_RULES` category list (overview, architecture, setup, operations, development, testing, security, roadmap, decisions, deployment, troubleshooting) — but there is no portfolio-wide rollup report |
| I-005 Stale knowledge report | not implemented | `CoverageRecord.state` already includes a `"stale"` value in its type signature, but nothing currently produces it or aggregates it |
| I-006 Conflict review queue | **complete** | `_conflict_index()` → `generated/indexes/conflicts.json` (`src/project_atlas/indexes.py`), fed by `knowledge_compiler.py`'s deterministic conflict detection |
| I-007 Dependency report | not implemented | `Relationship`/`RelationType` (`src/project_atlas/domain/relationships.py`) already defines `depends_on`, `provides`, `related_project`, `part_of`, etc. on `ConceptRecord.relationships`, but nothing aggregates these into a portfolio-wide dependency view |
| I-008 Capability report | not implemented | `ConceptType.CAPABILITY` already exists in the OKF taxonomy (`domain/vocabulary.py`); `RelationType.PROVIDES` already models "component provides capability"; no aggregation exists |

**Epic K — Pilot onboarding (0 of 7 complete):** no pilot fixture corpora,
expected manifests, expected generated vaults, or contradiction/secret
fixtures exist anywhere under `tests/fixtures/`. `docs/prp.md`'s MVP
boundary and final-acceptance criteria cannot be demonstrated without
them.

The recurring theme: **every remaining Epic I capability already has a
canonical, per-project or per-concept domain model to project from**
(`CoverageRecord`, `Maturity`, `Relationship`/`RelationType`,
`ConceptType.CAPABILITY`, `conflicts.json`). None of them require a new
canonical record type. What is missing is (a) portfolio-wide aggregation
across all `projects/*/` and (b) the pilot fixtures needed to exercise and
acceptance-test that aggregation, per `docs/plan.md`'s "evidence before
interpretation" and "no subjective trust scores" principles and this
repository's existing determinism conventions (`AGENTS.md` §Code and
design conventions).

## Decision

Establish **AS-MVP-001 — Portfolio Intelligence and Pilot Onboarding
Closure** as a bounded, deterministic, read-only-toward-canonical-state
extension, split into two internal workstreams (not separately certified
package IDs):

- **AS-MVP-001A — Portfolio Intelligence Completion**: implement the six
  remaining Epic I generators (I-002 through I-005, I-007, I-008) as pure
  projections over existing canonical state.
- **AS-MVP-001B — Pilot Onboarding and MVP Proof**: create three
  repository-native pilot fixtures (Epic K-001/K-002/K-003) with their
  expected manifests and expected generated vaults (K-004/K-005), plus
  contradiction and secret fixtures (K-006/K-007), and prove the complete
  pipeline against them.

`AS-MVP-001` does not reuse or redefine `AS-INT-001`, `AS-CORE-002`,
`AS-CORE-003`, `AS-ID-001`, `AS-SPEC-004`, `AS-RET-001`, `AS-SEC-001`, or
`AS-MAINT-001`.

### Canonical-state boundary

Portfolio intelligence remains strictly **derived, regenerable, read-only
toward canonical records, and non-authoritative**, matching the existing
three-layer vault model (`AGENTS.md`):

```
canonical source/project state (Layer A/B: state/*.json, projects/*/*.md)
  → deterministic portfolio projection (pure functions, no new writes to state/)
    → generated reports and indexes (Layer C: generated/portfolio/*.json + .md)
```

Portfolio generators MUST NOT write to `state/`, `projects/`, `sources/`,
`receipts/`, or any existing `generated/indexes/*.json` file, and MUST NOT
mutate source identity, project UUIDs, claims, concepts, lifecycle state,
architecture decisions, or evidence receipts. They read only:

- `state/claims/*.json`, `state/concepts/*.json` (existing, from
  `knowledge_compiler.py`)
- `projects/*/project.md` frontmatter and `ProjectRecord` fields
  (`coverage`, `concepts[].maturity`, `concepts[].relationships`)
- `generated/indexes/conflicts.json` (existing, unchanged, reused verbatim
  — not recomputed)
- `generated/reports/injection-findings.json` and
  `generated/reports/secret-findings.json` (metadata-only, for safe
  quarantine counts — never their content)

This mirrors the existing `retrieval.py` convention (AS-RET-001):
"read-only deterministic lexical exact/prefix retrieval; never mutates the
Vault."

### Generated-output boundary

New output root, following the existing `generated/indexes/` and
`generated/navigation/` convention:

```
generated/portfolio/
  overview.json              # I-002
  maturity-matrix.json       # I-003
  documentation-coverage.json # I-004 (aggregates existing CoverageRecord)
  stale-knowledge.json       # I-005
  dependency-report.json     # I-007
  capability-report.json     # I-008
generated/navigation/portfolio-overview.md   # human-readable projection
```

`generated/indexes/conflicts.json` (I-006) is already the conflict review
queue and is **not duplicated or moved**; portfolio overview links to it
by reference instead of recomputing conflict state, per §16's "it is a
view, not a workflow engine" requirement.

Each JSON file:

- `schema_version: 1` top-level key;
- `sort_keys=True`, deterministic key and array ordering (project IDs
  sorted lexicographically, category/state values from fixed controlled
  vocabularies, never filesystem enumeration order);
- every entry cites its source (`project_id`, and for coverage/maturity/
  dependency/capability entries, the `source_id`/`source_lineage_id` or
  concept ID it was derived from) — no uncited claim, matching "no claim
  without a traceable source";
- empty vault (`projects/` has zero subdirectories) produces valid,
  schema-conformant files with empty arrays, exit code 0 — never an
  exception (Scenario 6);
- an individual invalid/incomplete project is reported with an explicit
  `"status": "invalid"` entry and a reason, and does not abort generation
  of the other projects' entries (Scenario 7) — "fail closed" applies to
  writes, not to surfacing partial information about other projects.

Markdown human-readable projections may reference these JSON files but
must not introduce new frontmatter fields outside the existing OKF
profile.

### CLI integration

Add an explicit `atlas build-portfolio --vault <vault-dir>` command,
following the existing `build-indexes` pattern (its own subcommand,
argparse-registered in `cli.py`, `_promote(write_plan)`-boundary write,
exit codes 0/1/2 per existing convention). Portfolio generation is
**not** folded into `build-indexes` because `build-indexes` (AS-RET-001)
is a certified, narrowly-scoped lexical-retrieval-index generator; adding
unrelated portfolio aggregation to it would widen a certified package's
contract. The public workflow becomes:

```
atlas init
→ atlas discover
→ atlas ingest
→ atlas build-indexes
→ atlas build-portfolio
→ atlas validate
```

`atlas validate` is extended to reject a vault where
`generated/portfolio/*.json` is present but out of sync with a fresh
`build-portfolio` run (drift detection), mirroring the existing
`build-indexes` drift-rejection convention in `validation.py`.

### Maturity model

Categorical only, reusing the existing `Maturity` `StrEnum`
(concept → prototype → mvp → beta → production-candidate → production →
hardened). No numeric score is introduced (this repository's stated
principle is "no subjective trust scores," `AGENTS.md`). A project's
matrix entry reports:

- `maturity`: the `Maturity` value of that project's `Project Status`
  concept, or `"unknown"` if absent — never inferred from file count or
  heuristics;
- the **explicit inputs** behind it, reproducible from other generated
  files: `documentation_coverage_summary` (counts per coverage state from
  `documentation-coverage.json`), `open_conflicts` (count from
  `conflicts.json`), `validation_evidence_present` (bool, from whether the
  project has a `testing`/`validation` coverage category in `"present"`
  state).

No opaque score is produced; every field is a direct read of an existing
canonical or already-generated value.

### Documentation coverage / stale-knowledge

`documentation-coverage.json` aggregates the existing per-project
`coverage_for()` output (already computed and stored on `ProjectRecord`)
across all projects — it does not recompute coverage rules. Required vs.
optional categories, and the `absent`/`partial`/`present`/`stale`/
`conflicting` states, are exactly the existing `COVERAGE_RULES` categories
and `CoverageRecord.state` literal already defined in
`semantic_compiler.py`; AS-MVP-001 does not redefine them.

`stale-knowledge.json` (I-005) is the first consumer of the `"stale"`
state. Staleness is computed from the authoritative `modified_at`
(the discovery-time filesystem mtime already captured on `SourceRecord`,
per `discovery.py`) compared against a single configurable freshness
threshold (default 180 days) read from `[tool.atlas]` config, following
the existing `config.py` precedence chain (defaults → pyproject →
explicit config). A source with no `modified_at` is reported as
`"freshness": "unknown"`, never assumed fresh or stale. All freshness
tests use an injected reference `now` (a parameter, not `datetime.now()`
called inside the generator), consistent with NFR-001 ("no wall-clock
timestamps in generated content") — the reference date itself is supplied
by the caller (CLI reads real time once at the entry point; tests inject
a fixed date) and does not appear in the deterministic file body, only
derived category labels (`stale`/`fresh`/`unknown`) do.

### Dependency and capability reports

`dependency-report.json` (I-007) aggregates existing
`ConceptRecord.relationships` entries where `type == "depends_on"` or
`type == "related_project"`, grouped by project, each entry citing the
source concept ID. `capability-report.json` (I-008) aggregates concepts
where `ConceptType == "Capability"` and relationships where
`type == "provides"`, again citing source concept IDs. **No relationship
is inferred from prose.** A project with no declared relationships of a
given kind reports an empty list, not an inferred one; where evidence is
ambiguous the entry is omitted rather than guessed, per §17's
"unknown is preferable to an inferred relationship."

### Security boundary (AS-SEC-001 preserved)

Portfolio generators read `injection-findings.json` and
`secret-findings.json` **only** for their existing metadata fields
(`source_id`, `disposition`, `rule`, `confidence` — never the underlying
matched text, which those reports already never contain). A project's
portfolio entry may show `"quarantined_sources": 3` as a safe count; it
MUST NOT read `sources/imported-documents/` for quarantined source IDs
(quarantined sources never appear there, per AS-SEC-001) or otherwise
reconstruct/quote adversarial or secret content. No new detector logic is
introduced; AS-SEC-001's `quarantine.py`/`secrets.py` contracts are not
reopened or modified.

### Determinism

Every generated portfolio file: same canonical state in → same file set,
same key/array ordering, same bytes out. No wall-clock timestamps, random
IDs, unstable dict ordering, filesystem enumeration order, or absolute
paths in deterministic bodies. `json.dumps(..., sort_keys=True)` per
existing `indexes.py` convention. Two consecutive `build-portfolio` runs
against unchanged canonical state must be byte-identical (Scenario 8);
changing one pilot's source must change only that project's portfolio
entries and any portfolio-wide aggregate counts that reference it, not
unrelated projects' entries (Scenario 9).

### Pilot fixture model (Epic K)

Three repository-native fixtures under `tests/fixtures/pilots/`
(deterministic, offline, no live/personal documentation):

1. **`nebula` — mature and complete.** Full `.atlas-project.yaml`
   marker, `README.md`, `ARCHITECTURE.md`, one `docs/adr/`-style decision
   record, one validation-evidence document, one explicit
   `depends_on`/`provides` relationship pair. Expected result: `maturity`
   at or above `beta`, all required coverage categories `present`, zero
   open conflicts, zero stale findings.
2. **`black-agency-os` — partial and stale.** Only a `README.md` and one
   architecture note; no decisions, no validation evidence; one source
   file with a `modified_at` older than the freshness threshold (fixture
   files carry a fixed, injected mtime via the test harness, not the
   real filesystem clock). Expected result: several coverage categories
   `absent`/`partial`, at least one `stale-knowledge.json` entry, `unknown`
   or low maturity.
3. **`dark-factory` — conflicted and dependency-heavy.** Two sources
   with contradictory claims about the same field (feeding the existing
   conflict detector, producing a real `conflicts.json` entry), a
   `depends_on` relationship pointing at `nebula`, and a `provides`
   relationship with no corresponding capability consumer elsewhere.
   Expected result: a `conflicts.json`/portfolio conflict-queue entry
   referencing `dark-factory`, a cross-project dependency-report entry,
   lower/`unknown` maturity due to unresolved conflicts.

Expected manifests (K-004) and expected generated vaults (K-005) are
committed golden fixtures under `tests/fixtures/expected/`, compared
byte-for-byte in acceptance tests (mirroring the existing golden-file
convention for human-safe regeneration, backlog G-005). Contradiction
fixtures (K-006) and secret fixtures (K-007) reuse the `dark-factory`
project for conflicts and add one credential-shaped string to a fourth,
minimal fixture project to exercise the existing `secrets.py` quarantine
path end-to-end through the new portfolio layer (proving quarantined
counts appear safely, per the security boundary above).

## Acceptance criteria (closes PRP §8 success metrics for portfolio/pilot scope)

10 scenarios, each an executable `tests/integration/test_as_mvp_001_*.py`
test:

1. All three pilots appear in `overview.json`, `maturity-matrix.json`,
   and `documentation-coverage.json`.
2. `nebula` (mature) is not reported missing/stale/partial for any
   category it actually satisfies.
3. `black-agency-os` (partial) receives exactly the expected
   absent/partial/stale findings, no false positives or negatives.
4. `dark-factory` appears in the conflict review queue with stable
   `source_id`/`source_lineage_id` references.
5. Declared `depends_on`/`provides` relationships appear in
   `dependency-report.json`/`capability-report.json` in deterministic
   (sorted) order, each citing its source concept.
6. An empty vault (`atlas init` only, no projects ingested) produces
   valid, schema-conformant, empty-array portfolio files with exit code
   0.
7. Injecting one structurally invalid project (missing required
   `project.md` frontmatter) produces an `"status": "invalid"` entry for
   that project only; the other two pilots' entries are unaffected and
   `build-portfolio` exits non-zero only for the invalid project's own
   validation, not a hard crash.
8. Two consecutive `build-portfolio` runs against unchanged state are
   byte-identical (`sha256sum` over every file in `generated/portfolio/`).
9. Changing one pilot's source (e.g. adding a decision record to
   `black-agency-os`) changes only that project's coverage/maturity
   entries and portfolio-wide aggregate counts; `nebula` and
   `dark-factory`'s entries are byte-identical before/after.
10. `atlas validate` fails closed when `generated/portfolio/*.json` is
    stale relative to canonical state (drift), mirroring the existing
    `build-indexes` drift-rejection test pattern.

## Alternatives rejected

- **Numeric/weighted maturity score.** Rejected: violates "no subjective
  trust scores" (`AGENTS.md`); an opaque score is explicitly disallowed
  by this ADR's own governance directive.
- **Inferring dependencies/capabilities from prose via NLP/embeddings.**
  Rejected: out of scope (no semantic/vector retrieval, no LLM scoring
  per this ADR's exclusions); the canonical `Relationship` model already
  supports explicit declaration, which is authoritative.
- **Folding portfolio generation into `build-indexes`.** Rejected: would
  widen the certified AS-RET-001 contract; kept as an explicit
  `build-portfolio` command instead.
- **Live/DevDrive or personal-document pilots.** Rejected per explicit
  exclusion below; pilots are repository-native, deterministic fixtures
  only.
- **A single combined "AS-MVP-001" certification covering both
  workstreams as one indivisible unit.** Considered acceptable for this
  entry gate (internal A/B subdivision only, not separate certified IDs)
  because both workstreams share one canonical-state boundary and one
  acceptance-test matrix; may be split into separately certified
  packages later if implementation scope proves too large for one cycle.

## Explicitly out of scope

Unrestricted DevDrive ingestion; live personal-document ingestion;
semantic/vector retrieval; embeddings; LLM scoring; graph database
adoption; multi-Vault federation; remote connectors; dashboard UI;
autonomous remediation; portfolio write-back into canonical state; new
security detector behavior; reopening AS-SEC-001 semantics. These may be
proposed later as separate v2 work packages.

## Migration impact

None to existing canonical state, schemas, or certified packages.
Additive only: new `generated/portfolio/` directory, new
`build-portfolio` CLI subcommand, new pilot fixtures under
`tests/fixtures/pilots/` and `tests/fixtures/expected/`. No change to
`src/project_atlas/quarantine.py`, `secrets.py`, `ingestion.py`'s
`_promote` boundary, or any AS-SEC-001/AS-MAINT-001 file.

## Implementation sequencing

1. **AS-MVP-001A, step 1:** `documentation-coverage.json` and
   `overview.json` (pure aggregation of existing `CoverageRecord`s and
   project list — lowest risk, no new domain concepts).
2. **AS-MVP-001A, step 2:** `maturity-matrix.json` (reuses step 1's
   output plus existing `Maturity` concept field and `conflicts.json`).
3. **AS-MVP-001A, step 3:** `stale-knowledge.json` (introduces the
   freshness-threshold config and injected-reference-date test pattern).
4. **AS-MVP-001A, step 4:** `dependency-report.json` and
   `capability-report.json` (reuses existing `Relationship`/
   `RelationType`/`ConceptType.CAPABILITY`).
5. **AS-MVP-001A, step 5:** `atlas build-portfolio` CLI command and
   `atlas validate` drift-rejection extension.
6. **AS-MVP-001B, step 1:** `nebula` fixture + expected manifest/vault
   golden files.
7. **AS-MVP-001B, step 2:** `black-agency-os` and `dark-factory`
   fixtures + expected golden files.
8. **AS-MVP-001B, step 3:** contradiction and secret fixtures (K-006,
   K-007) layered onto the existing three pilots.
9. **AS-MVP-001B, step 4:** the 10 acceptance-scenario integration
   tests, run against all three pilots together.
10. Independent certification and owner merge, following the same
    architecture-rereview / independent-verification pattern established
    by AS-SEC-001 and AS-MAINT-001.

Each step is independently testable and mergeable to a review branch
before the next begins; no step requires touching AS-SEC-001,
AS-MAINT-001, or any other certified package's files.
