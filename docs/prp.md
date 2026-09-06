Product Requirements Prompt — Project Atlas

1. Product definition

Project Atlas is a local-first project knowledge compiler. It scans approved documentation sources, classifies and normalizes them, extracts evidence-backed concepts, and generates a structured Obsidian vault following an internal Open Knowledge Format profile.

The result is both:

a human-readable portfolio operating system; and

an agent-readable knowledge substrate.

2. Problem statement

Project documentation is distributed across repositories, local folders, exported reports, Markdown files, PDFs, office documents, agent outputs, and deployment evidence. Existing documentation frequently suffers from:

inconsistent naming;

duplicate or superseded records;

unclear authority;

stale status claims;

missing provenance;

disconnected architecture and decisions;

poor cross-project discoverability;

no consistent portfolio view;

inability to produce safe, bounded AI context.

3. Users

Primary user

The portfolio owner who needs to supervise multiple technical projects, identify status, understand evidence, and direct coding agents.

Secondary users

implementation agents;

architecture reviewers;

security reviewers;

operations agents;

future collaborators;

portfolio and product planning agents.

4. User outcomes

The user can answer:

Which projects exist?

What is each project’s purpose, maturity, and current status?

Which documentation is canonical?

What changed recently?

Which claims are verified?

What dependencies exist across projects?

Which decisions remain open?

Which risks and documentation gaps require attention?

What context should be provided to an agent for a specific task?

5. Functional requirements

FR-001 Vault initialization

Create a valid vault scaffold containing system, portfolio, project, capability, infrastructure, technology, decision, standards, source, generated, and template areas.

FR-002 Source discovery

Discover supported documents from approved roots and create a source manifest containing:

stable source ID;

path or URI;

content hash;

media type;

size;

timestamps;

repository information when available;

likely project;

classification state;

exclusion reason when excluded.

FR-003 Duplicate detection

Detect exact duplicates by cryptographic hash. Record near-duplicate candidates without deleting or merging them automatically.

FR-004 Classification

Classify sources by project, document type, lifecycle, authority, subject, and likely canonical status. Deterministic rules must run before optional model-assisted classification.

FR-005 Text extraction

Extract text from MVP-supported formats:

Markdown;

plain text;

YAML;

JSON;

TOML;

HTML;

PDF when a parser is available;

DOCX when a parser is available.

Unsupported files remain listed in the manifest.

FR-006 Concept generation

Generate atomic concept notes for projects, components, architecture, decisions, requirements, work packages, milestones, validation, deployments, environments, risks, issues, runbooks, standards, repositories, releases, datasets, metrics, findings, and agent instructions.

FR-007 Provenance

Every generated concept must identify its supporting sources. Claim-level provenance is preferred for critical fields such as status, version, deployment state, test results, and dates.

FR-008 Contradiction handling

Detect incompatible claims and create an explicit conflict record. Never silently choose a value without documenting the alternatives.

FR-009 Human-edit preservation

Generated sections must be clearly delimited. Regeneration must preserve protected human sections byte-for-byte.

FR-010 Index generation

Generate progressive index.md files for major directories and project bundles.

FR-011 Portfolio views

Generate:

portfolio overview;

maturity matrix;

project health view;

documentation coverage view;

stale knowledge report;

dependency overview;

shared capability overview;

open risks and decisions;

recent changes.

FR-012 Validation

Validate:

YAML frontmatter;

required metadata;

identifiers;

links;

provenance;

lifecycle values;

stale dates;

orphan notes;

duplicate concept IDs;

missing required project documents.

FR-013 Incremental refresh

On a repeated run, process only changed, added, removed, or impacted source records. Preserve stable IDs wherever possible.

FR-014 Context packs

Produce bounded context bundles for:

development;

architecture;

security;

deployment;

executive review.

FR-015 Audit log

Record generation events, source changes, conflicts, validation failures, and human promotion events.

6. Non-functional requirements

NFR-001 Determinism

The fixture pipeline must produce byte-identical output across repeated runs on the same platform, excluding explicitly allowed timestamps.

NFR-002 Offline operation

All MVP tests and fixture ingestion must work without internet access.

NFR-003 Portability

The vault must remain readable as plain Markdown without Obsidian.

NFR-004 Safety

Secrets and likely credentials must be detected and excluded or redacted before generated output is written.

NFR-005 Performance

A corpus of 10,000 small Markdown files should complete discovery and hashing without loading all content into memory.

NFR-006 Extensibility

Parsers, classifiers, generators, validators, and provider integrations must use explicit interfaces.

NFR-007 Traceability

Every generated file must include generation metadata and source references.

7. MVP boundary

The MVP includes:

scaffold generation;

local directory discovery;

Markdown and text ingestion;

exact duplicate detection;

deterministic classification;

project and source concepts;

protected-region updates;

index generation;

validation reports;

three pilot fixtures.

The MVP may defer:

semantic near-duplicate merging;

full PDF table extraction;

OCR;

cloud connectors;

autonomous canonical promotion;

advanced knowledge graph storage;

live Obsidian plugin development.

8. Success metrics

100% of generated project notes have source provenance.

0 human-protected regions modified during regeneration.

100% of generated internal links resolve.

100% of fixture conflicts are surfaced.

100% repeat-run idempotency for unchanged sources.

0 secrets from fixtures appear in generated vault output.

All pilot projects produce a project overview, source index, gap report, and status confidence state.

9. Deliverables

Python package and CLI;

vault scaffold;

JSON schemas;

templates;

fixture corpus;

unit, integration, and acceptance tests;

example generated vault;

operator documentation;

migration and extension guidance.

10. Final acceptance

The project is MVP-complete when a clean environment can run:

python -m pytest
atlas init --output .tmp/vault
atlas discover --source tests/fixtures --output .tmp/manifest.json
atlas ingest --manifest .tmp/manifest.json --vault .tmp/vault --source tests/fixtures
atlas build-indexes --vault .tmp/vault
atlas validate --vault .tmp/vault

and all commands exit successfully while producing a traceable, deterministic vault.
