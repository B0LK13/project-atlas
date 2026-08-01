# Acceptance Tests

## AT-001 Initialize vault

Given an empty target directory, `atlas init` creates the required root structure and system notes.

## AT-002 Discover files

Given the fixture corpus, discovery produces one source record per included file and records excluded files with reasons.

## AT-003 Exact duplicates

Given two byte-identical files, discovery assigns distinct source paths but groups them under one duplicate hash.

## AT-004 Stable manifests

Given unchanged fixtures, two discovery runs produce semantically identical manifests.

## AT-005 Deterministic classification

Given known filenames and headings, classification assigns the expected document types without network access.

## AT-006 Unknown remains unknown

Given an ambiguous document, classification uses `unknown` rather than inventing a type.

## AT-007 Generate project note

Given classified sources for a project, ingestion creates `project.md` with required metadata and source references.

## AT-008 Provenance

Every generated concept has at least one resolvable source reference.

## AT-009 Conflict detection

Given sources that report different deployed versions, a conflict record is created and the project note discloses the unresolved conflict.

## AT-010 Human preservation

Given a generated note containing a protected human region, regeneration preserves that region byte-for-byte.

## AT-011 Malformed markers

Given unbalanced protection markers, regeneration exits non-zero and does not modify the file.

## AT-012 Link validation

All generated internal Markdown links resolve.

## AT-013 Path safety

A source path containing traversal sequences cannot cause writes outside the vault root.

## AT-014 Secret protection

A fixture containing a fake API key does not emit the key into generated Markdown or logs.

## AT-015 Portfolio overview

All pilot projects appear in the generated portfolio overview with status, maturity, review state, and freshness information.

## AT-016 Documentation coverage

Each pilot project receives a coverage report listing present, partial, missing, and stale documentation categories.

## AT-017 Incremental update

Changing one fixture updates only the expected manifest record and impacted generated concepts.

## AT-018 Removed source

Removing a source marks dependent concepts for review and does not silently preserve unsupported claims as verified.

## AT-019 Context pack

A development context pack includes project overview, architecture, active work package, decisions, standards, risks, and recent validation within configured size limits.

## AT-020 Clean run

The complete clean fixture pipeline exits successfully and produces no error-severity validation findings.
