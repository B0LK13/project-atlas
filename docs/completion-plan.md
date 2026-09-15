# Project Atlas — Completion Plan and Task Backlog

**Prepared:** 2026-08-01
**Basis:** full read of `docs/` (`plan.md`, `prp.md`, `acceptance-test.md`,
`backlog.md`, `implementation-roadmap.md`, `master-roadmap.md`, `adr/`),
`AGENTS.md`, `WORKLOG.md`, and a live check of both test suites in this
repository.

---

## 1. Critical finding: two unrelated programs share this repository

Before any backlog is useful, this has to be named explicitly: **this
repository currently contains two different products, both calling
themselves "Project Atlas," that do not share code and have almost no
progress overlap.**

| | **Track 1 — OKF Vault Compiler** | **Track 2 — Documentation/Governance Control Plane** |
|---|---|---|
| Defined by | `AGENTS.md`, `docs/prp.md`, `docs/plan.md`, `docs/backlog.md`, `docs/implementation-roadmap.md` | `docs/master-roadmap.md`, `AGENT-BOOTSTRAP.md`, `atlas-vault-documentation/*` |
| What it does | Scans a project's own documentation, classifies it, and generates a source-backed OKF/Obsidian vault (`project.md`, `status.md`, portfolio views, etc.) | Forces AI coding agents to capture, normalize (via an external `mda-cli`), verify, and route "work session events" through a governed pipeline, plus a Graphify relationship-graph adapter |
| Lives in | `src/project_atlas/` (the installable `project-atlas` package) | `atlas-vault-documentation/` (explicitly excluded from the package's ruff/mypy `include`, and **not run in `.github/workflows/ci.yml`**) |
| Progress per its own tracker | `docs/backlog.md`: Epics A–B done (14/14 items), **Epics C–K not started (0/59 items)** | `WORKLOG.md`: AS-WP-001 → AS-WP-005, AS-SKILL-001 and AS-CTRL-001 certified; Atlas Core vertical slice remains pending |
| CLI surface today | `atlas version`, `atlas init` only. `discover`, `ingest`, `build-indexes`, `validate` (needed for `prp.md` §10 final acceptance) **do not exist** | `atlas_agent.py doctor/run`, `capture_event.py`, `normalize_event.py`, `route_event.py`, `discover_projects.py`, `ingest_project.py`, `ingest_graphify.py`, ~20 other scripts |

Corroborating evidence this is a genuine fork, not just two names for one plan:

- `AGENTS.md` — the file explicitly written to onboard agents to this repo —
  lists `plan.md`, `prp.md`, `implementation-roadmap.md`, `acceptance-test.md`,
  `backlog.md` as "the authoritative specification." **It never mentions
  `master-roadmap.md` or `atlas-vault-documentation/` at all.**
- `pyproject.toml`'s own comment says sibling directories dropped at the repo
  root "are separate deliverables with their own tooling" — written by the
  agent that did WP-001, the same day Track 2 started.
- `master-roadmap.md` and `WORKLOG.md` disagree with each other: the roadmap
  still lists AS-WP-005 as "Next capability after control-plane
  certification" (§11) while `WORKLOG.md` records it as already certified,
  and lists AS-SKILL-001 as certified in its status table while also
  presenting it as pending in the phase-10 narrative. The roadmap was not
  kept in sync with the worklog it's supposed to govern.
- Track 2's own domain model (raw/normalized "agent work events", routing
  state, Graphify nodes/edges) has no relationship to Track 1's domain
  model (`SourceRecord`, `ConceptRecord`, `Claim`, `ConflictRecord`, …). No
  code, schema, or test is shared between them.

**What this means practically:** "complete the project" is ambiguous until
someone decides which of these two things *is* the project. Sections 5 and 6
below give each track its own backlog so either can be executed, but §4
gives a recommendation and this needs a decision before large amounts of
work go into either one.

A secondary, cross-cutting finding: **there is no git repository here**
(`git status` fails with "not a git repository"). Two parallel work
programs with ~250 files and no version control is a real risk — see §7.

---

## 2. Verified current state (commands actually run just now)

```
$ .venv/bin/python -m pytest                     # Track 1 — src/project_atlas
54 passed

$ .venv/bin/python -m ruff check .                # Track 1
All checks passed!

$ .venv/bin/python -m mypy src                    # Track 1
Success: no issues found

$ cd atlas-vault-documentation && ../.venv/bin/python -m pytest   # Track 2
run 1: FAILED tests/test_agent_control.py::test_managed_launcher_automates_ack_capability_and_postflight
        AssertionError: concurrent managed-launcher run returned
        "verification-failed" for one of two parallel agents
run 2 (immediate rerun, same code): 149 passed, 0 failed
```

Track 1 is exactly as its own backlog says: foundation-only, solid, green.

Track 2 has a **flaky concurrency bug** in precisely the capability
(shared-Vault multi-agent safety) that `AS-CTRL-001`'s own completion report
(`atlas-vault-documentation/AS-CTRL-001-COMPLETION-REPORT.md`) lists as an
open certification blocker. This is not a documentation gap, it's a live,
reproducible race condition — first item in the Track 2 backlog below.

---

## 3. What "done" means for each track

- **Track 1 is done** when `docs/prp.md` §10's final acceptance sequence
  (`atlas init`, `atlas discover`, `atlas ingest`, `atlas build-indexes`,
  `atlas validate` against `tests/fixtures`) exits 0 end-to-end, all 20
  acceptance tests (`docs/acceptance-test.md`) pass, and `docs/backlog.md`
  Epics C–K are checked off.
- **Track 2 reaches "Atlas Beta"** (per `master-roadmap.md` §17) when
  AS-CTRL-001 is certified; it reaches "1.0" only after Phases 6–11
  (cross-project model, real-project pilot, estate sync, dashboard,
  hardening) — a program of a size comparable to Track 1 itself.

---

## 4. Recommendation

Finish **Track 1 first**, and treat Track 2 as paused/optional until that
decision is made explicitly. Reasoning:

1. Track 1 is the product `AGENTS.md` — the file future agents actually
   read first — says this repository is for. Track 2 was never folded into
   that spec.
2. Track 1 is 19% done by its own item count (14/73 backlog items) with a
   clean, tested foundation; Track 2 is a much larger, still-uncertified
   program bolted onto the side that also depends on an external tool
   (`mda-cli`) that has **never been run for real** — every certification
   to date used a mocked binary.
3. Track 2's stated purpose is to govern how agents document work on
   *other* projects. Standing it up before Track 1 exists means building
   governance for a product that doesn't have any documented output yet to
   govern.

If Track 2 is in fact the priority (e.g. it's meant to become the
onboarding/governance layer for a wider portfolio and that's the actual
goal), say so and the sequencing in §6 can move to the front instead — the
backlog below works either way, only the order changes.

---

## 5. Track 1 backlog — OKF Vault Compiler to MVP

This sequences the existing `docs/backlog.md` Epics C–K against
`docs/implementation-roadmap.md`'s phases, and adds two epics
(**L**, **M**) that the roadmap requires but `backlog.md` never created
items for. Each phase's exit gate is from `implementation-roadmap.md`;
requirement IDs are from `docs/prp.md` / `docs/acceptance-test.md`.

### Phase 1 — Discovery (Epic C, 8 items) — FR-002, FR-003, AT-002/003/004/013
Recursive scanner honoring `DiscoveryConfig.include_globs` /
`exclude_globs` (already defined, unused, in `src/project_atlas/config.py`);
MIME/extension detection; streaming SHA-256 (NFR-005: no full-file loads,
must handle 10k files); exact-duplicate grouping by hash; manifest writer
producing `SourceRecord` instances validated against
`schemas/source-record.schema.json`; unsupported-file reporting;
path-traversal tests reusing `scaffold.validate_output_path`'s posture.
New CLI subcommand: `atlas discover --source <dir> --output <manifest.json>`.

### Phase 2 — Parsing and classification (Epics D + E, 14 items) — FR-004, FR-005, AT-005/006
Markdown/YAML-frontmatter/plain-text parsers behind a parser registry
(NFR-006 explicit interfaces); heading and link extraction; deterministic
classification rules in priority order (explicit override → path → filename
→ frontmatter → heading), each result carrying a `classification_state`
and a method-audit field; ambiguous input classifies `unknown`, never
invents a type (AT-006).

### Phase 3 — Concept generation (Epic F, 7 items) — FR-006, FR-007, AT-007/008
Stable ID strategy (must survive incremental reruns, needed by Phase 7);
frontmatter renderer matching the `ConceptRecord`/`Claim`/
`ProvenanceReference` schemas already shipped; project-note renderer
implementing the `project.md` template in `docs/plan.md` §4; source
reference and conflict renderers (feeds Epic G's conflict handling —
FR-008, AT-009); deterministic ordering everywhere (NFR-001); atomic
writes (reuse `scaffold._write_atomic`). New CLI subcommand:
`atlas ingest --manifest <manifest.json> --vault <dir>`.

### Phase 4 — Human-safe regeneration (Epic G, 5 items) — FR-009, AT-010/011
Protected-marker parser for the `<!-- BEGIN/END GENERATED|HUMAN -->`
convention already emitted by `scaffold._template_content`; generated-region
replacement that leaves human regions byte-identical; fail-closed on
unbalanced markers (exit non-zero, zero writes — AT-011); golden-file tests.
This is a prerequisite for Phase 3's re-run behavior once Phase 7 lands.

### Phase 5 — Indexes and portfolio reports (Epic I, 8 items) — FR-010, FR-011, AT-015/016
Progressive `index.md` generation for every bundle; portfolio overview,
maturity matrix, documentation coverage, stale-knowledge report, conflict
queue, dependency and capability reports as described in `docs/plan.md`
§10–13. New CLI subcommand: `atlas build-indexes --vault <dir>`.

### Phase 6 — Validation framework (Epic H, 10 items) — FR-012, NFR-004, AT-012/013/014
Validator interface (NFR-006) with built-ins: YAML, schema, link, provenance,
lifecycle, freshness, orphan, **secret scanner** (NFR-004/AT-014 — no fixture
secret may reach generated output or logs), coverage; severity-driven exit
codes (`Severity.ERROR/WARNING/INFO` already defined in
`domain/vocabulary.py`). New CLI subcommand: `atlas validate --vault <dir>`.
Completing this subcommand is what makes `prp.md` §10's final acceptance
sequence runnable for the first time.

### Phase 7 — Incremental operation (Epic J, 6 items) — FR-013, AT-017/018
State cache; added/changed/removed source detection; impact graph from
source → generated concept (built on Phase 3's stable IDs); selective
regeneration; removed-source handling that marks dependents for review
rather than silently keeping stale claims verified (AT-018).

### Phase 8 — Context packs (**new Epic L** — `backlog.md` has no epic for
this despite `implementation-roadmap.md` Phase 8 and `prp.md` FR-014/AT-019)
- L-001 Context profile configuration (development/architecture/security/
  deployment/executive, per `docs/plan.md` §15)
- L-002 Development pack assembler
- L-003 Architecture pack assembler
- L-004 Security pack assembler
- L-005 Deployment pack assembler
- L-006 Executive pack assembler
- L-007 Size-limit enforcement and traceable-only content (AT-019)

### Phase 9 — Optional provider adapters (**new Epic M**, stretch/deferred)
`implementation-roadmap.md` frames this as optional; MVP boundary in
`prp.md` §7 doesn't require it to ship. Sequence last, only if MVP (Phases
1–8) is complete and there's remaining scope appetite.
- M-001 Provider-neutral interface (NFR-006)
- M-002 Mock provider for offline tests
- M-003 Schema-constrained response validation
- M-004 Offline fallback (disabling providers must leave MVP functional)
- M-005 Audit logging of provider calls (model output must never bypass
  provenance or validation, per `AGENTS.md`)

### Epic K — Pilot onboarding (7 items, runs alongside Phases 1–8, not after)
`docs/backlog.md` already defines K-001..K-007 (fixture corpora for
Nebula/Black Agency OS/Dark Factory, expected manifests, expected generated
vault, contradiction and secret fixtures). These fixtures are what every
phase above needs to test against (AT-001–AT-020 all reference "the fixture
corpus"), so K-001/002/003 (the three corpora) should be created **early**,
alongside Phase 1, not deferred to the end — every subsequent phase's exit
gate depends on them existing.

**Sequencing note:** Phases 1→2→3 are strictly sequential (each consumes
the previous phase's output). Phase 4 can start as soon as Phase 3's
renderer exists. Phase 5 needs Phase 3 output for real content but can be
scaffolded against Phase 1 output alone. Phase 6 (validation) should be
built incrementally alongside each phase rather than saved entirely for the
end — e.g. the link validator only makes sense once Phase 5 exists.

---

## 6. Track 2 backlog — Documentation/Governance Control Plane

### P0 — Fix the certification blockers already identified by the project's own reports
1. **Fix the concurrent-capture race condition** reproduced in §2
   (`tests/test_agent_control.py::test_managed_launcher_automates_ack_capability_and_postflight`).
   One of two agents writing to a shared Vault concurrently gets
   `verification-failed`. This is the exact failure mode
   `AS-CTRL-001-COMPLETION-REPORT.md` lists under "Shared-Vault multi-agent
   operation" as unproven — it's not unproven, it's failing intermittently.
   Root-cause in the router/verification path (`atlas-vault-documentation/internal/`,
   `scripts/route_event.py`) before claiming certification.
2. Run `atlas-agent run` against a disposable Vault with a **real** local
   MDA executable (or an explicitly-scoped, documented mock accepted as
   permanent) and capture the full normalize→verify→route session receipt
   end to end (completion-report blocker #1).
3. Synchronize an offline spool and prove duplicate-free replay
   (completion-report blocker #2).
4. Add/run the direct-protected-path and supervised-subagent probes
   (completion-report blocker #3).
5. Reconcile `master-roadmap.md` against `WORKLOG.md` (§1 above) — the
   status tables for AS-WP-005 and AS-SKILL-001 currently contradict the
   phase narratives in the same document.

### P1 — Close the CI gap
`atlas-vault-documentation/tests/` (149 tests) never runs in
`.github/workflows/ci.yml` — only `src/` and `tests/` (Track 1) do. Every
"certified" claim to date has been verified by hand, not by a repeatable
gate. Add a second CI job (or step) that runs the subproject's suite, ruff,
and mypy if it's meant to stay part of this repository.

### P2 — Phase 6, AS-WP-005 hardening
`WORKLOG.md` records AS-WP-005 (Graphify adapter) as certified, but
`master-roadmap.md` §11 still calls it "next capability" and its exit
criteria include "no canonical override by derived Graphify data" and
"incremental graph replay" — re-verify these against the same live-run
standard being required for AS-CTRL-001 above, given the roadmap/worklog
disagreement.

### P3 — Phases 7–11 (`master-roadmap.md` §12–16)
Only after AS-CTRL-001 is genuinely certified (program gate stated in the
roadmap itself, §10.2): AS-WP-006 (cross-project knowledge model),
AS-WP-007 (bounded real-project pilot — the roadmap already names candidate
projects: Nebula, Black Agency OS, Dark Factory, AI Budget Coach,
Autonomous Loop), AS-WP-008 (estate-wide sync), AS-WP-009 (search/dashboard),
AS-WP-010 (production hardening). Each is its own multi-week program: treat
this document's §5 for Track 1 as the level of detail each of these will
need once reached, not something to plan item-by-item now.

---

## 7. Cross-cutting backlog (applies regardless of track priority)

- **Initialize version control.** No `.git` exists. ~250 files of
  uncommitted, unreviewable work across two programs is the single biggest
  operational risk in this repository right now. `git init`, a `.gitignore`
  audit (one already exists — confirm it covers `.venv/`, `.tmp/`,
  `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`), and an
  initial commit should happen before further feature work, so all of the
  above can be tracked incrementally instead of as one undifferentiated
  blob.
- **Decide and document the Track 1 / Track 2 relationship** in `AGENTS.md`
  itself (currently silent on Track 2's existence) so future agents don't
  have to re-derive the finding in §1.
- **`docs/backlog.md` is missing Epics L and M** (§5) — add them so the
  file stays the single source of truth for Track 1 progress.

---

## 8. Suggested next three actions

1. Confirm the Track 1 vs. Track 2 priority call (§4).
2. If Track 1: create the three pilot fixture corpora (K-001–K-003) first,
   then implement Phase 1 discovery (Epic C) against them — this unblocks
   every subsequent phase's exit gate.
3. If Track 2: fix the concurrency race condition (§6 P0.1) before anything
   else — it's a correctness bug, not a scope gap, and it's currently
   masked by the fact that the subproject suite isn't in CI (§6 P1).
