# Atlas 3.0 — Architecture

| Field | Value |
|---|---|
| Directive | D-191 |
| Status | **CANONICAL PROGRAM ARCHITECTURE** |
| Runtime namespace | `src/project_atlas/atlas3/` |
| Temporal engine | Reuse AS-2.0-TEMPORAL-001 — no second clock |

## 1. Stack

```text
EVIDENCE → TRUTH → TIME → CAUSALITY → INTENT → PROOF → AUTONOMY
```

Transport (CLI, Python API, LIVE_API, Web, TUI, MCP, A2A) is **not** a layer
in this stack. Surface ≠ authority. Transport must not alter truth semantics.

## 2. Reuse map (program level)

```text
REUSED_COMPONENTS =
  Truth Core (knowledge_compiler, claims, conflicts, UNKNOWN, authority)
  source lineage / project identity
  bitemporal catalog + kdiff (AS-2.0-TEMPORAL-001 / AS-2.2-KDIFF-001)
  Ask2 + Context Compiler (runtime_22 / context_pack)
  handoffs / session capture / conversation_capture
  security boundaries (secrets, authz, path guards, quarantine)
  MCP read-only allow-list
  orchestration DAG / leases / owner gates / certification receipts
  Coder Alpha lenses (overview, state, changed, decisions, unknown, brief, next)
  ChatGPT export bridge + Knowledge Inbox (compose, do not replace)
  graph relationship store (AS-GRAPH-003; derived only)
  fixture twin production (AS-2.0-TWIN-001; fixture-waiver honesty)

NEW_COMPONENTS =
  atlas3 engineering event model (AT3-003)
  atlas3 universal event ledger (AT3-014)
  atlas pulse lens (AT3-015)
  atlas start compiler (AT3-030)
  agent proof-of-work (AT3-050)
  twin domain vocabulary + relationship catalog
  provider-neutral LLM connector / envelope / extract / reconcile (D-192)
  future UX projections (Home, Timeline, explorers) over these contracts

MIGRATION_REQUIRED =
  NO for Truth Core, temporal engine, ChatGPT bridge, MCP, or demo surfaces
  YES only as additive derived stores under generated/ops/atlas3/
  YES for historical roadmap classification (already applied; files kept)

COMPATIBILITY_RISK =
  LOW if Atlas 3 stays in src/project_atlas/atlas3/ + additive CLI
  HIGH if any package rewrites knowledge_compiler, bitemporal, chatgpt_bridge,
    api_server, authz, discovery, or ingestion
```

## 3. Three-layer vault (unchanged)

| Layer | Role | Atlas 3 may |
|---|---|---|
| A — Evidence | Imported sources, agent events, quarantined conversations | Append derived event/memory evidence under `generated/ops/atlas3/` |
| B — Truth | Claims, authoritative state, conflicts | Read only until a separately governed promotion package exists |
| C — Derived | Portfolio, lenses, graph, twin, pulse, start | Write derived projections only |

Twin output is Layer C. Twin ≠ Layer B authority.

## 4. Digital twin domain

### 4.1 Canonical nodes

| Node | Meaning | Landed substrate |
|---|---|---|
| Project | Governed project identity | `projects/`, source identity |
| Repository | VCS root | discover/connect inventory |
| Component | Buildable/logical unit | architecture lens |
| Service | Runtime service | twin/estate fixtures (fixture-only today) |
| File | Source path | discovery inventory |
| Symbol | Code symbol | **NEW** (not a Core index today) |
| Claim | Evidence-backed assertion | Truth Core claims |
| Decision | Accepted or proposed decision | decisions lens + conversation items |
| Requirement | Required behavior | claims / docs |
| Task | Work item | orchestration + proof chain |
| Agent | Actor identity | agent events / adapters |
| PR | Pull request | **NEW event kind** (ledger) |
| Commit | VCS commit | **NEW event kind** (ledger) |
| Test | Test run/result | **NEW event kind** (ledger) |
| Build | CI build | **NEW event kind** (ledger) |
| Deployment | Environment deploy | **NEW event kind** (ledger) |
| Incident | Failure/incident | ops + ledger |
| Artifact | Build/output artifact | backup/ops receipts |
| Environment | Named runtime env | twin fixture / **NEW** |

### 4.2 Canonical relationships

Every derived relationship requires provenance.

| Relationship | Reuses | Notes |
|---|---|---|
| CONTAINS | graph `part-of` | Alias in twin vocabulary |
| IMPLEMENTS | **NEW alias** | File/symbol implements requirement/claim |
| DEPENDS_ON | graph `depends-on` | |
| CLAIMS | Truth Core | Node asserts a claim |
| CONTRADICTS | graph `conflicts-with` + Core conflicts | Graph ≠ auto conflict |
| SUPERSEDES | graph `supersedes` | |
| VALIDATES | graph `validates` | |
| INVALIDATES | **NEW** | Stronger later evidence |
| CAUSED_BY | **NEW** | Causal layer; derived |
| DECIDED_BY | **NEW** | Intent/decision actor |
| DEPLOYED_AS | **NEW** | Service → environment |
| OBSERVED_IN | **NEW** | Fact observed in evidence |
| OWNED_BY | **NEW** | Fail-closed owner identity |
| DERIVED_FROM | graph `derived-from` | |
| BLOCKS | **NEW** | Task/conflict blocks task |

Atlas 3 twin relationships are **derived**. They never auto-write Layer B.

## 5. Temporal contract

Reuse `project_atlas.bitemporal.evaluate_as_of` and the
`generated/ops/bitemporal/` catalog.

All material twin facts support, where applicable:

| Field | Meaning |
|---|---|
| `VALID_FROM` | Document-declared valid-time start |
| `VALID_TO` | Document-declared valid-time end |
| `OBSERVED_AT` | When evidence was observed |
| `RECORDED_AT` | When Atlas recorded the fact |

Rules:

- Do not introduce a second temporal engine.
- Do not use wall-clock `now` as a silent valid-time.
- Conversation time, retrieval time, and supersession time are observations,
  not a competing clock.

## 6. Event architecture

```text
Agent events (atlas_contracts) ──┐
Ops events (ops_events.py)       ├─► AT3-003 normalize ─► AT3-014 ledger
Conversation captures            │         ▲
Engineering signals (PR/CI/git) ─┘         │
                                           │ read-only
Coder Alpha lenses / kdiff / ask2 ─────────┘
```

AT3-014 writes **only** `generated/ops/atlas3/ledger/`.
It must not dual-write `generated/ops/events/` (`ops_events.py` forbids that).

## 7. Interoperability

| Surface | Status on main | Atlas 3 rule |
|---|---|---|
| CLI | Landed | Additive commands only |
| Python API | Landed modules | New `project_atlas.atlas3` public surface |
| LIVE_API | Read-only 127.0.0.1 | No new write routes in this slice |
| Web | Derived UX | UX follows contracts; UI ≠ truth |
| TUI | Not shipped | Future; same contracts |
| MCP | Read-only allow-list | No memory write tool |
| A2A | Not shipped | Future transport; same envelope |

## 8. Security model (program)

| Threat | Response |
|---|---|
| Path escape | Fail closed; reuse `safe_relative_component` |
| Secret echo | `scan_text`; never persist matched secrets |
| Forged owner decision | `FALSE_OWNER_DECISION` without `owner_origin` |
| Forged project id | Fail closed routing |
| Prompt injection in conversation | Quarantine; never auto-promote |
| Provider spoof | Connector records `import_mode` + capability honesty |
| Cross-project leak | Project identity required; ambiguous → fail |
| Demo-surface mutation | Isolated `atlas3/` namespace |

Detail: [llm-memory/SECURITY.md](llm-memory/SECURITY.md).

## 9. Isolation from certified demo surfaces

Do not mutate while `FULL_LIVE_DEMO_READY = NO`:

- `discovery.py`, `ingestion.py`
- `api_server.py`, `authz.py`
- `knowledge_compiler.py`
- `chatgpt_bridge.py`, `chatgpt_capture.py` (prep-frozen 2.2 surface)
- `compat_anchor.py`, `conflict_projections.py`, `reality_gap.py`
- Golden fixture `tests/fixtures/demo/estate/harbor-api`

Additive CLI registration in `cli.py` is allowed if existing command behavior
is unchanged.

## 10. First-vertical data flow

```text
EngineeringEvent (AT3-003)
        │
        ▼
Universal ledger (AT3-014)
        │
        ├─► Pulse (AT3-015)  ── what changed / matters / stale / conflicts / failed / decided / next
        ├─► Start (AT3-030) ── bounded briefing + token budget
        └─► Proof (AT3-050) ── TASK→…→POST-MERGE evidence chain

LLM connectors (AT3-035+) remain a parallel isolated plane.
They feed quarantine / inbox / atlas3 memory stores, not Truth Core.
```
