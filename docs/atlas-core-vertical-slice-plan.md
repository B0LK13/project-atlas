# Atlas Core Vertical Slice — Work Package Plan

**Branch:** `feat/atlas-core-vertical-slice`  
**Baseline:** `atlas-reconciliation-baseline-2026-08-01` / `672cd4e`  
**Scope:** controlled fixtures only; `discover → ingest → build-indexes → validate`

## Authority mapping

| Slice obligation | Authoritative source | Implementation evidence |
|---|---|---|
| deterministic, safe source discovery | `AGENTS.md` core conventions; `docs/prp.md` FR-002, FR-003, NFR-004/005; `docs/backlog.md` C-001–C-008 | `src/project_atlas/discovery.py`, manifest tests |
| text-native parsing and deterministic classification | `docs/prp.md` FR-004/005; `docs/plan.md` source taxonomy; `docs/backlog.md` D/E | `src/project_atlas/ingestion.py`, classification report |
| source-backed generated project records | `docs/prp.md` FR-006/007; `docs/acceptance-test.md` AT-007/008 | project notes and imported-source links |
| deterministic indexes | `docs/prp.md` FR-010; `docs/plan.md` vault structure; `docs/backlog.md` F-006, I-001 | `src/project_atlas/indexes.py` |
| strict structure, provenance and link validation | `docs/prp.md` FR-012, NFR-007; `docs/acceptance-test.md` AT-012/013/020 | `src/project_atlas/validation.py` |
| unchanged replay is a no-op | `AGENTS.md` incremental-refresh rule; `docs/prp.md` FR-013; `docs/acceptance-test.md` AT-004/017 | stable manifest hash and byte/hash replay test |
| unsupported and sensitive sources remain explicit | `AGENTS.md` safety rules; `docs/prp.md` FR-002/005, NFR-004; `docs/acceptance-test.md` AT-014 | excluded manifest records and security fixtures |

## Deliverables

1. `atlas discover --source <root> --output <manifest>` writes a stable JSON
   manifest with source IDs, hashes, media types, project identity,
   exclusions and duplicate groups.
2. `atlas ingest --manifest <manifest> --vault <vault>` copies eligible source
   evidence, classifies text-native records, and generates provenance-backed
   project notes and documentation maps.
3. `atlas build-indexes --vault <vault>` deterministically rebuilds project,
   portfolio and source indexes.
4. `atlas validate --vault <vault>` rejects missing generated structure,
   escaping links and broken internal links.
5. Controlled fixture tests prove a complete workflow and stable discovery
   replay without broad project scanning.

## Explicit non-goals

This slice does not modify Atlas Control Plane internals, implement Graph
Layer ingestion, add provider/LLM behavior, perform estate-wide scanning, or
claim completion of the full Core MVP. Human-safe regeneration, conflicts,
coverage and incremental source deletion remain later Core work packages.

## Exit gates

- all Core tests pass;
- Ruff, mypy and compilation pass for `src/` and `tests/`;
- controlled fixture workflow reaches strict validation;
- unchanged discover and compile reruns produce no content changes;
- no Control Plane files are modified by this work package;
- commit is made on `feat/atlas-core-vertical-slice` and references the
  baseline commit.
