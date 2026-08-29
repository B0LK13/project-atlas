# ADR-033 — Phase 2A: specification-backed autonomous work origination

**Status:** accepted for isolated Phase-2A implementation
**Date:** 2026-08-29
**Scope:** D-PHASE2A-SPECIFICATION-ORIGINATION-POC-FINALIZATION
**Baseline:** `SEALED_BASELINE_HEAD = d09557fd03e34ec1c8daaeb505ad25815d0fc408`
(`^{tree} = 2a3029238673c503f73d93dd6bc0f49b14c8f685`) — verified identical
to `origin/main` at the time this ADR was written; not rewritten or
reinterpreted here.

## CURRENT_PIPELINE

Two systems already exist and are preserved unchanged by this ADR:

1. **`orchestration/autonomy/discovery.py:discover()`** — a fixed tuple
   of 6 historical `DiscoveryCandidate` records (real closed/superseded
   package ids: `AS-ORCH-001D-R2/R6/R7`, `AS-ORCH-001D`, `AS-ORCH-001E`,
   the pilot package). `governor.ingest_discovery()` can only
   materialize a `WorkNode` for exactly one of them (`_pilot_node()`),
   which hardcodes the pilot's own objective/mutation-surface/acceptance
   criteria. This is orchestration-fixture enumeration, not general
   project discovery, and this ADR does not expand that list.
2. **`project_roadmap.py` / `project_next.py` (`roadmap_unlock`)** — a
   real, generic parser (`_parse_fenced_record`) that reads a `##
   Roadmap record` fenced JSON block (schema `atlas.project-roadmap.v1`)
   and normalizes it into structured items (id, title, status,
   lifecycle, `depends_on`, `evidence`, `blockers`). It is
   **vault-coupled**: `_load_roadmap_source()` only reads from
   `<vault>/projects/<id>/roadmap.md` or a compiled `<vault>/projects/<id>/project.md`
   — never from a project's own working tree.

Both the governed DAG/lease/dispatch machinery (`models.py`, `dag.py`,
`leases.py`, `lease_projection.py`, `dispatcher.py`, `loop.py`) and the
owner-gate machinery (`owner_gates.py`, `NodeState.OWNER_HELD`) are
real, general-purpose, and reused unchanged by this ADR. `WorkNode`
already has the shape needed to carry a specification-derived work item
(`objective`, `mutation_surface`, `acceptance_criteria`,
`iv_requirements`, `owner_gate`, `risk_tags`) with hard Pydantic
invariants (`destructive`, `merge_authorized`, `execution_authorized`
are always `Literal[False]` — a `WorkNode` can never self-grant
authority). No parallel task-management architecture is introduced.

## MISSING_BOUNDARY

`CROSS_PROCESS_ORIGINATION = UNPROVEN` at the sealed baseline because:

1. **No path from real specification evidence to a `WorkNode`.**
   `roadmap_unlock` requires a *pre-structured* fenced JSON record; it
   does not extract facts from prose requirements, ADRs, or test files.
   Nothing upstream of it produces that record from a project's actual
   documents.
2. **No durable, general `WorkNode` persistence.** `rehydration.py`
   rebuilds the governor fresh on every process start; only
   `LoopState` persists. Only the pilot package can be rehydrated
   because it is "the only node shape the governor knows how to
   deterministically rebuild from inventory alone"
   (`rehydration.py:36-42`); any other `package_id` fails closed with
   `NODE_NOT_REHYDRATABLE` rather than fabricate a node whose mutation
   surface / acceptance criteria were never durably recorded. This is
   the direct cause of `CROSS_PROCESS_ORIGINATION = UNPROVEN`: even if
   a proposal existed, it could not survive a real process restart.
3. **A related, already-discovered, owner-reserved gap that this ADR
   deliberately routes around rather than fixes**: `estate-manifest.json`
   (`/mnt/d/Atlas-Demo/manifests/`) records a 2026-08-29 re-verification
   showing that a prior fenced-roadmap-record successor revision for
   the Gamma/TASK-017 estate, though internally correct, does **not**
   survive the real `discover → ingest → build-indexes → validate`
   pipeline — the semantic compiler does not carry a source document's
   raw fenced block through into the compiled `project.md`, so
   `build_roadmap_lens` against a freshly ingested vault still returns
   `you_are_here=UNKNOWN`. That finding is explicitly logged as
   `UNDERSPECIFIED_PRODUCT_SEMANTIC / MISSING_LENS`, an owner-only
   product-design question, "not a bug to fix unilaterally." **This ADR
   does not touch the semantic compiler or vault-ingestion path.**
   Instead, the new adapter (below) reads a project's own working tree
   directly — "NORMAL PROJECT SOURCES" per the directive — and reuses
   only the pure parsing function (`_parse_fenced_record`), never the
   vault-ingestion round trip. This keeps Phase 2A inside
   `EXPLICITLY_SPECIFIED_BUT_UNSTRUCTURED_WORK` territory and out of the
   parked product decision.

## SOURCE FACT MODEL

New package `src/project_atlas/orchestration/origination/`. `facts.py`
defines:

- `SourceFactKind` (`StrEnum`): `AUTHORITATIVE_ROADMAP_ITEM`,
  `CORROBORATING_SPEC_TEST`. (Deliberately not a general "requirement /
  ADR / spec" taxonomy — see Fail-closed paths: only these two kinds
  currently have a deterministic, non-LLM extraction method. Adding a
  third kind is a future extension, not silently inferred.)
- `SourceFact` (frozen Pydantic model): `kind`, `project_id`,
  `location` (path relative to the project root, never absolute, never
  containing `..`), `content_digest` (sha256 of the exact bytes read —
  deterministic identity, no wall-clock timestamp per NFR-001), and a
  bounded `excerpt` (never the full file — keeps provenance auditable
  without becoming a second copy of the source).

Extraction (`adapter.py`) is two independent, generic scanners, each
usable on any project root with no knowledge of TASK-017 specifically:

- `extract_authoritative_facts(project_root, project_id)` — reads
  `<project_root>/docs/ROADMAP.md` if present, calls the **existing**
  `project_atlas.project_roadmap._parse_fenced_record` (imported, not
  reimplemented) and `_normalize_item`-equivalent evidence resolution
  rewritten against the *project root* instead of a vault (the existing
  `_normalize_item` is vault-coupled — see `_evidence_exists(vault, ...)`
  — so this adapter has its own `_evidence_exists_in_project()` doing
  the identical path-safety check against `project_root`). Every parsed
  item with `lifecycle in {"READY"}` and `status in {"NOT_STARTED",
  "IN_PROGRESS"}` becomes one `AUTHORITATIVE_ROADMAP_ITEM` fact.
- `extract_corroborating_facts(project_root, evidence_paths)` — for
  each evidence path an authoritative item declares, if the path
  resolves to a real file under the project root and that file's first
  200 lines contain a module-level `pytestmark = pytest.mark.skip(...)`
  or `pytestmark = pytest.mark.xfail(...)` (regex, not import/exec of
  the file — never execute untrusted project code), record one
  `CORROBORATING_SPEC_TEST` fact carrying the skip/xfail reason string
  as its excerpt.

Generic by construction: nothing here matches on "TASK-017", a
filename, or any string from the Gamma estate. Any project with a
roadmap fenced record whose evidence includes a skip/xfail-marked test
file produces the same two fact kinds.

## ORIGINATION PROPOSAL MODEL

`proposal.py` — `OriginationProposal` (frozen Pydantic model), fields
exactly per the directive's contract: `work_id`, `project_id`, `title`,
`intent`, `why_this_work`, `why_now`, `source_evidence` (tuple of
`SourceFact`), `source_locations` (tuple of paths, derived, redundant
with `source_evidence` for cheap inspection), `authoritative_source`
(the one `SourceFact` of kind `AUTHORITATIVE_ROADMAP_ITEM`),
`acceptance_evidence` (tuple of `SourceFact` of kind
`CORROBORATING_SPEC_TEST`), `success_criteria` (tuple of strings —
copied verbatim from the roadmap item's own `evidence`/title, never
invented), `dependencies`, `blockers`, `contradictions` (tuple of
strings — populated only by the policy gate, never by the adapter),
`proposed_scope` (a `MutationSurface`-shaped path allow-list, reused
from `orchestration.models`), `risk_class`, `authority_class`,
`evidence_completeness`, `provenance` (adapter version id + the exact
`content_digest`s consulted — enough to prove replay-stability without
re-reading the source), `origination_identity` (see Identity model,
below).

`why_this_work` / `why_now` are template-filled from the structured
facts (item title, item status, roadmap "Next (specified, not
implemented)" section membership) — **never free-form model prose**.
If a human/LLM step adds narrative color in a future wave, that text
is documentation, not authority; the fields above must remain
reconstructable from `source_evidence` alone with no model in the loop.

## POLICY GATE

`policy.py` — pure, deterministic, no LLM call. `evaluate(proposal) ->
PolicyResult`:

1. **Evidence quorum**: `AUTHORITATIVE_INTENT_SIGNAL = YES` iff
   `authoritative_source` is present and its `SourceFact.location`
   resolves to a real file. `CORROBORATING_ACCEPTANCE_OR_INCOMPLETE_SIGNAL
   = YES` iff `acceptance_evidence` is non-empty. Both required for
   `EXECUTION_READY` to even be considered; otherwise
   `ORIGINATION_PROPOSAL = VALID` (if intent alone is present) but
   `EXECUTION_READY = NO`, `REASON = INSUFFICIENT_ACCEPTANCE_CONTRACT`.
2. **Contradiction check**: if two `AUTHORITATIVE_ROADMAP_ITEM` facts
   for the same `project_id` disagree on the same item id's `status`
   (only possible if the adapter is ever pointed at two conflicting
   roadmap sources for one project — defensive, not reachable in the
   single-source POC), `EXECUTION_READY = NO`, `REASON =
   CONFLICTING_PROJECT_EVIDENCE`.
3. **Insufficient-alone sources are structurally unreachable, not just
   prompted against**: the adapter has no extraction path that ever
   produces a `SourceFact` from a bare TODO comment, an LLM suggestion,
   commit activity, a general README idea, or an unrelated failing
   test — those inputs simply never become a `SourceFact` in the first
   place, so no policy rule has to reject them after the fact. This is
   the "preserve the distinction structurally" requirement.
4. **Risk classification** (`risk.py`, O1 — see below) runs after the
   quorum passes and can independently force `EXECUTION_READY = NO` /
   route to `OWNER_HELD` regardless of evidence completeness.

## ROADMAP_UNLOCK / DAG INTEGRATION

A proposal that clears the policy gate is materialized into a real
`WorkNode` by `materialize.py:materialize_work_node(proposal) ->
WorkNode` — a pure mapping (objective ← intent, mutation_surface ←
proposed_scope, acceptance_criteria ← success_criteria, risk_tags ←
derived from risk classification), **not a new execution path**. From
that point on the node moves through the existing, unmodified
`dag.py` / `leases.py` / `dispatcher.py` / `loop.py` machinery exactly
like any other `WorkNode`: `READY → LEASED → ACTIVE → VERIFYING →
CERTIFIED → OWNER_HELD` (autonomous transition to `MERGED` remains
forbidden by `dag.py` regardless of origination source). `roadmap_unlock`
itself is not modified; this ADR's adapter is additive and sits
upstream of, not inside, `project_roadmap.py`.

## FAIL_CLOSED_PATHS

- No authoritative fact → no proposal is created at all (not
  "proposal with reason=none").
- Authoritative fact present, no corroborating fact →
  `EXECUTION_READY = NO`, `INSUFFICIENT_ACCEPTANCE_CONTRACT`.
- Conflicting authoritative facts for one item → `EXECUTION_READY = NO`,
  `CONFLICTING_PROJECT_EVIDENCE`.
- Roadmap item status already `IMPLEMENTED` / `VERIFIED_COMPLETION`, or
  lifecycle `CLOSED`/`MERGED` → excluded at extraction time (not a
  `READY`/`NOT_STARTED` item), never reaches the policy gate.
- Roadmap item lifecycle outside the fenced record entirely (e.g. a
  `## Later` prose bullet with no fenced-record entry) → never parsed
  into a fact at all — `_parse_fenced_record` only sees the JSON block.
- Risk classification finds any O1-disqualifying attribute (dependency
  change, workflow/CI file, credential, security/auth surface,
  destructive data op, irreversible migration, deployment/infra change,
  external spend, history rewrite, governance widening, or scope
  outside the specification) → node routes to `OWNER_HELD` via the
  existing `owner_gates.py`, never self-executes.
- Rehydration finds a persisted `WorkNode` record that is missing or
  fails its own Pydantic schema validation → `find_materialized_work_node()`
  returns `None`, and `rehydration.py` falls through to the pre-existing
  `NODE_NOT_REHYDRATABLE` fail-closed outcome — never fabricates a
  substitute. **Correction (independent-IV finding, D-PHASE2A):** this
  is schema validation only, not a re-verification of
  `provenance.consulted_digests` against the live project source on
  disk — the durable `origination.json` store is trusted the same way
  `lease_projection.json` already is, not independently re-checked
  against reality on every rehydration. Doing the latter would require
  also durably recording the project root path (not currently part of
  the persisted record) so a later process could re-read and re-hash
  the original evidence files; that is a real, deliberately deferred
  strengthening for a future wave, not implemented in this one. An
  earlier draft of this ADR overclaimed a
  `hash-mismatch → ORIGINATION_NOT_REHYDRATABLE` check that does not
  exist in code; this paragraph corrects that.
- Text found inside scanned project documents is parsed only as data
  (regex/JSON extraction) — never executed, never sent to an LLM as an
  instruction, never interpreted as a command to Atlas. An
  instruction-shaped sentence inside a roadmap/ADR/test docstring
  changes nothing about extraction behavior.
- Duplicate discovery / restart replay → see Identity model below;
  same identity ⇒ same record, not a second proposal.

## IDENTITY / DEDUPLICATION MODEL

`identity.py` — `origination_identity(project_id, authoritative_source)
-> str`: `sha256(f"{project_id}::{authoritative_source.location}::
{authoritative_source.content_digest}")`, hex-encoded, no wall-clock
component. Stable across:

- process restarts (pure function of durable inputs),
- re-scans that find the same unchanged evidence (idempotent — the
  persistence layer treats a re-derived identity as "already known",
  not a new record),
- and instance renames/re-runs (the identity depends only on project
  id, evidence location, and the exact byte content already consulted,
  not on wall-clock time or an incrementing counter).

If the underlying evidence file's content changes, `content_digest`
changes, so the identity changes too — an intentionally stale-evidence
signal (a changed file produces a genuinely new identity rather than
silently reusing a proposal whose provenance no longer matches disk).
Persistence (`projection.py`, mirroring the existing
`lease_projection.py` atomic-write pattern) is keyed by this identity;
the extraction pipeline checks the projection before creating a new
proposal, satisfying `NO_DUPLICATE_ORIGINATION` and
`PROVENANCE_SURVIVES_RESTART` structurally, not by convention.

## Consequences

- `AI_INVENTED_WORK` remains structurally unreachable: every field in
  `OriginationProposal` traces to a `SourceFact`, and every `SourceFact`
  traces to a specific byte range already present in the project's own
  repository before Atlas ran.
- This ADR does not reopen or resolve the parked
  `GAMMA_NEXT_WORK_PRIORITY` / semantic-compiler product question in
  `/mnt/d/Atlas-Demo/manifests/estate-manifest.json`; it deliberately
  builds a path that does not depend on its resolution.
- Merge authorization is not granted by this ADR.
