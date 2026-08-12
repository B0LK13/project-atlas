# D-PROJECT-ATLAS-CODER-ALPHA-035 — Phase 2 Journey Audit

| Field | Value |
|---|---|
| Directive | `D-PROJECT-ATLAS-CODER-ALPHA-035` Phase 2 |
| Scope | Audit implemented capabilities vs user journey (no status inflation) |
| Base | `main` @ `322f55b56162bf324b8e5b19fb9759dffd0c7518` |
| Classification vocabulary | `IMPLEMENTED` \| `PARTIAL` \| `MISSING` \| `DEMO_ONLY` \| `NOT_PRODUCTIZED` |
| Honesty | `DEMO_FIXTURE != AUTHENTIC_PILOT`; fixture E2E ≠ daily dogfood productization |

## Classification rules used

- **IMPLEMENTED** — real product path exists on Core/web/control-plane for authentic (non-fixture-only) use, with concrete modules/commands.
- **PARTIAL** — substantive substrate exists, but the journey step is incomplete, multi-command tribal, dual-path, or not dogfood-ready.
- **MISSING** — named journey command/surface absent (`atlas handoff`, Cursor auto-context). `atlas connect` shipped under AS-CODER-ALPHA-CONNECT-001.
- **DEMO_ONLY** — works only / primarily over DEMO_FIXTURE or demo stubs; not authentic productization.
- **NOT_PRODUCTIZED** — contract/scaffold/registry/stub exists; not a stranger-usable product flow.

---

## Journey audit table

| # | Step | Status | Evidence (exists) | Absence / gap |
|---|---|---|---|---|
| 1 | FRESH PROJECT | **PARTIAL** | `atlas connect .` binds+compiles a fresh tree; `atlas init` → `scaffold.py`; `atlas doctor` → `doctor.py`; onboard docs + Windows scripts; control-plane `atlas_agent.py init-project` writes `.atlas/project.yaml` | Stranger path still Windows/DEMO_FIXTURE-oriented in older onboard docs (`docs/productization/install/LIMITATIONS.md`); post-connect knowledge lenses not auto-populated |
| 2 | `atlas connect .` | **IMPLEMENTED** *(AS-CODER-ALPHA-CONNECT-001)* | `atlas connect` → `src/project_atlas/connect.py` + CLI in `cli.py`; bind at `.atlas/connect.json`; default vault `<project>/.atlas-vault`; Core chain with SEC-002 rediscover | Post-connect knowledge/ask auto-materialization and Cursor injection remain later backlog items |
| 3 | Atlas understands project | **PARTIAL** | Core compile on ingest: `src/project_atlas/ingestion.py` calls `compile_knowledge` + `compile_project_record` → `projects/<id>/project.md`, claims/concepts/conflicts; pipeline `discover`→`ingest`→`build-indexes`→`build-portfolio`→`validate` proven in `tests/integration/test_as_demo_2_2_golden_fixture.py` | Operator must run multi-command choreography; `generated/answers/` **not** auto-emitted after Core pipeline (`docs/demo/DEMO-FINDINGS.md` DEMO-FINDING-001; `src/project_atlas/web_api/knowledge.py`) |
| 4 | Human opens Atlas Knowledge / Obsidian | **PARTIAL** | Obsidian-compatible vault scaffold (`scaffold.py` dirs + Markdown); web Knowledge lens `apps/web/src/pages/production/KnowledgePage.tsx` + nav `ProdNav.tsx`; LIVE_API `atlas live api-serve` → `src/project_atlas/api_server.py` `/v1/knowledge` | Obsidian modules are **non-plugin registries only**: `src/project_atlas/obsidian_ux.py`, `obsidian_workspace.py` (`plugin_shipped: false`); Knowledge UI empty unless operator seeds `generated/answers/`; demo stub fallback when API down |
| 5 | "What is this project?" | **PARTIAL** | `atlas ask2` → `src/project_atlas/ask2.py` (hybrid retrieve + p2 context compiler); `atlas query` → `knowledge_query.py`; project note from `semantic_compiler.py`; golden KNOWN ask in demo integration test | No first-class conversational product UX; web `/v1/ask` uses **substring inventory match** `ask_atlas_live.py`, not Ask2; ChatGPT gateway project-status is **DEMO_FIXTURE** (`integrations/chatgpt-atlas/atlas_gateway.py`) |
| 6 | "What changed?" | **PARTIAL** | `atlas kdiff` → `src/project_atlas/knowledge_diff.py`; AppService `kdiff_*`; API `/v1/kdiff`; web `TimeMachinePage.tsx` + `useLiveTimeMachine.ts`; portfolio bitemporal via `build-portfolio` (`portfolio.py`) | Requires prepared vault + portfolio catalogs + operator-known as-of/T1/T2; not automatic after connect; not NL "what changed since yesterday" |
| 7 | "What decisions matter?" | **PARTIAL** | Decision claims → `projects/<id>/decisions.md` via `knowledge_compiler.render_bundle`; agent-event decision projection in `ingestion.py` (`decisions` bucket); vault `decisions/` scaffold area | No dedicated ask shape / CLI / web lens that answers the journey question; ranking/importance of decisions not productized |
| 8 | "What is unknown/conflicting?" | **PARTIAL** | Conflicts + reviews from `knowledge_compiler.py` → `review/conflicts/<project>.json`, `review/pending/<project>.json`, `conflicts.md`; Ask2 `status ∈ {known,unknown,conflict}`; API `/v1/conflicts`; Time Machine conflicts panel | Web Knowledge/Ask-live plane depends on seeded answers; no single dogfood command that returns unknowns+conflicts+reviews together for a project without tribal flags |
| 9 | "What should I do next?" | **MISSING** | Substrate only: review queue, blockers projection (`ingestion.py` `blockers`), stale-knowledge portfolio (`portfolio.py`), reality-gap **product** inventory (`reality_gap.py` — Atlas 1.0→2.0 gaps, not project next-work) | No productized next-actions synthesizer/command/UI; north-star listed in `docs/plan.md` §1 but not shipped as journey step |
| 10 | Cursor receives Atlas Context | **NOT_PRODUCTIZED** | Context primitives: `atlas context-pack build` → `context_pack.py`; `atlas runtime compile` → `runtime_22.py`; MCP read invoke `atlas live mcp-invoke` → `mcp_server.py` / `mcp_registry.py`; repo bootstrap `AGENT-BOOTSTRAP.md` | No Cursor IDE integration (no product `.cursorrules`/MCP install path that injects Atlas context into Cursor). ChatGPT MCP gateway is separate **DEMO_FIXTURE** (`integrations/chatgpt-atlas/`) |
| 11 | Coding session | **NOT_PRODUCTIZED** | Optional wrap: `atlas-vault-documentation/scripts/atlas_agent.py run` (governed skill lifecycle for this repo) | Coding itself is external; Atlas does not productize a coding-session workspace for arbitrary projects |
| 12 | Automatic meaningful session capture | **PARTIAL** | Explicit capture: `atlas_agent.py document`, `capture_event.py`, `document_work.py`; skill contract `atlas-vault-documentation/skill/SKILL.md`; ingest of agent events into vault (`ingestion.py`); ChatGPT export bridges `chatgpt_capture.py` / `chatgpt_bridge.py` | **Not automatic** — requires agent/operator to call document/capture; no IDE hook watching Cursor sessions |
| 13 | `atlas handoff` | **MISSING** | Internal graph helper `handoff_quarantine_store` in `graph_relationships.py` (AS-GRAPH-004); control-plane `postflight`/`receipt` closeout | No `atlas handoff` CLI/product command for cross-agent resume packs |
| 14 | Different agent resumes | **PARTIAL** | Session state `.atlas/sessions/` (`agent_control/session.py`); event state under vault; receipt gate; Ask2/context-pack/query can re-read Truth Core | Resume is manual ritual (`atlas_agent` bootstrap/preflight/document), not "open different agent and receive handoff automatically" |
| 15 | Human knowledge updates | **PARTIAL** | Protected human regions preserved (`semantic_compiler.py`, `knowledge_compiler.py` markers; scaffold HUMAN blocks); re-`discover`/`ingest` for source changes; knowledge-inbox receipt stub `knowledge_inbox.py` (≠ authority promote); web POST `/v1/actions` is action ledger only (`api_server.py`) | No productized human edit → review → promote UX; inbox explicitly never promotes Layer B |
| 16 | Same Truth Core underneath | **IMPLEMENTED** | Single vault Truth Core: Layer A sources + Layer B compile (`knowledge_compiler.py` / `semantic_compiler.py`) + indexes (`indexes.py`) + validate (`validation.py`); read facades share adapters (`app_service.py` → `web_api/*`); UI≠canonical / graph≠authority / model≠authority stamped across ask2/API/web | Dual **read lenses** (Ask2 vs `ask_atlas_live`) and DEMO_FIXTURE estates exist, but authority remains vault Core — not a second truth store |

---

## Surface inventory (quick reference)

| Surface | Path / command | Journey role |
|---|---|---|
| CLI connect | `atlas connect` | Steps 1–3 (bind+compile) |
| CLI Core pipeline | `atlas init\|discover\|ingest\|build-indexes\|build-portfolio\|validate` | Steps 1,3,16 |
| CLI ask / query / diff / context | `atlas ask2`, `atlas query`, `atlas kdiff`, `atlas context-pack`, `atlas runtime` | Steps 5–8,10 |
| CLI live | `atlas live api-serve`, `atlas live mcp-invoke` | Steps 4,5,8,10 |
| Web | `apps/web` routes `/knowledge`, `/time-machine`, `/projects`, … | Steps 4,6,8 |
| MCP Core | `src/project_atlas/mcp_server.py` allow-listed reads | Step 10 (primitive) |
| MCP ChatGPT demo | `integrations/chatgpt-atlas/` | **DEMO_ONLY** status/search |
| Control plane | `atlas-vault-documentation/` + `atlas_agent.py` | Steps 11–14 (governed, explicit) |
| Obsidian | vault Markdown output; `obsidian_ux.py` / `obsidian_workspace.py` contracts | Step 4 (scaffold ≠ plugin) |

---

## Top 3 highest-value MISSING/PARTIAL gaps (unblock daily dogfood)

1. **Auto-materialize the live ask/knowledge plane from Core compile (close DEMO-FINDING-001)** — After `atlas connect` / a real pipeline, `generated/answers/` stays empty, so web Knowledge + `/v1/ask` + MCP knowledge reads look "unknown" even when claims/conflicts exist under `state/` and `review/`. Wire answer-lens emission (or point live ask at Ask2/Core indexes) so steps 5–8 work on authentic projects without demo seeding.

2. **Cursor context + explicit handoff + automatic-or-default session capture** — Steps 10–14 are the coding loop. Primitives exist (`context-pack`, `runtime compile`, agent `document`/`postflight`), but there is no product `atlas handoff`, no Cursor injection path, and capture is opt-in ritual. A minimal dogfood loop: export context pack for Cursor → capture meaningful events by default in `atlas_agent run` → `atlas handoff` receipt another agent can resume from the same Truth Core.

3. **Project Overview / Current State / What Changed dogfood lenses** — Ask2/kdiff substrate exists; stranger-usable defaults immediately after connect do not.

---

## Explicit non-claims

- This audit does **not** claim `AUTHENTIC_PILOT = PASS`, `RELEASE CERTIFIED`, or `ALPHA_READY`.
- Golden DEMO_FIXTURE Ask/KDiff PASS (`tests/integration/test_as_demo_2_2_golden_fixture.py`) proves Core contracts on fixtures — **not** stranger daily dogfood productization.
- `TECHNICAL_DEMO_VERIFIED` / web ACCEPTED labels elsewhere do not upgrade MISSING `handoff` or NOT_PRODUCTIZED Cursor injection.
