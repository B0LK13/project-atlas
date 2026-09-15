# AS-CORE-002 — Semantic Domain Model and Source Lifecycle Plan

**Branch:** `feat/atlas-core-semantic-lifecycle`  
**Status:** certified after post-merge verification

## Requirement mapping

| Slice | Authoritative requirements | Delivery |
|---|---|---|
| Versioned semantic records | `AGENTS.md`; PRP FR-006, FR-007, FR-012; backlog B-002–B-007 | Extend existing Pydantic domain records with explicit schema versions and lockstep schemas. |
| Rich project compilation | PRP FR-006–FR-010; acceptance AT-007–AT-009, AT-015–AT-016; backlog F-001–F-006, I-001, I-004 | Compile validated project metadata, claims, provenance, authority, coverage and event references without inventing facts. |
| Source lifecycle | PRP FR-003, FR-013, FR-015; acceptance AT-003, AT-017–AT-018; backlog J-001–J-006 | Persist source state, detect added/changed/removed/restored/duplicate/conflicting records, and retain tombstones. |
| Secret protection | PRP NFR-004; acceptance AT-014; backlog H-008 and CORE-SEC-001 | Scan content before copying; emit redacted metadata-only findings and never write confirmed secrets. |
| Authority and coverage | `docs/plan.md` sections 5–7 and coverage section; acceptance AT-009, AT-016 | Use explicit authority/lifecycle states and deterministic present/partial/missing/stale/conflicting coverage. |
| Regeneration safety | PRP FR-009; acceptance AT-010–AT-011; backlog G-001–G-005 and F-007 | Preserve human regions, reject malformed markers, compare before write, and retain atomic replacement. |

## Boundaries and non-goals

This package extends the existing `atlas discover → ingest → build-indexes →
validate` workflow. It does not begin Graphify work, replace the Control Plane,
or invent missing project facts. Unknown semantic fields remain explicit.

## Validation ladder

1. Semantic model and schema lockstep tests.
2. Source lifecycle, secret, authority, coverage and regeneration tests.
3. Public CLI fixture workflow and unchanged replay.
4. Core, Control Plane and repository suites plus Ruff, mypy and compilation.

## Review remediation checkpoint

Agent Two identified two blockers in commit `575ce3b`: the semantic schema did
not constrain nested arrays, and persisted source state was not revalidated.
Commit `bb2a713` closes both defects and adds a preflight that prevents a
malformed generated marker in one project from causing partial writes to
another project. Commit `f970e72` extends that preflight to an in-memory
write plan covering imported sources, event-package copies, project pages,
documentation maps, state, reports and projections. Agent Two independently
replayed the corrected failure and recommended merge.

Post-merge evidence is recorded in
[`AS-CORE-002-post-merge.md`](AS-CORE-002-post-merge.md) and
[`AS-CORE-002-post-merge-receipt.yaml`](evidence/AS-CORE-002-post-merge-receipt.yaml).
