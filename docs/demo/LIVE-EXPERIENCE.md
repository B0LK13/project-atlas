# Atlas LIVE Experience — DEMO_FIXTURE end-to-end

> **DEMO_FIXTURE** · **AUTHENTIC_PILOT = FALSE** · **NOT RELEASE EVIDENCE**
>
> `D-PROJECT-ATLAS-CLOUD-LIVE-EXPERIENCE-001` · security gate unchanged (external).

This runbook shows the **current** Atlas product working end to end LIVE — real
`atlas` pipeline → real `LIVE_API` → real Web UI projections — against a safe,
isolated `DEMO_FIXTURE` estate. It uses production commands only; no backend
capabilities were added to make the demo look richer, and no authentic pilot is
claimed. `DEMO_FIXTURE != AUTHENTIC_PILOT`.

## Reconciled reality

- `CURRENT_MAIN`: `f420e4e` (`origin/main` at execution time).
- `DEMO_FIXTURE`: `tests/fixtures/demo/estate/` — 3 projects: `harbor-api`,
  `harbor-ops`, `harbor-portal` (canonical `AS-DEMO-2.1-001` corpus).
- Security-owned surfaces (ingestion, discovery, `api_server.py`, `authz`,
  scheduler, autonomy, openai/chatgpt bridges, control-plane, Windows scripts)
  were **not** modified. Unmerged PR #253 surfaces (`apps/web/playwright.config.ts`,
  `apps/web/e2e/**`, `.cursor/**`) were **not** touched.

## 1. Run the real pipeline

```bash
atlas init          --output .tmp/live-vault
atlas discover      --source tests/fixtures/demo/estate --output .tmp/live-manifest.json
atlas ingest        --manifest .tmp/live-manifest.json  --vault .tmp/live-vault
atlas build-indexes --vault .tmp/live-vault
atlas validate      --vault .tmp/live-vault
atlas build-portfolio --vault .tmp/live-vault
```

Observed (all exit `0`):

| Stage | Result |
| --- | --- |
| discover | 16 sources |
| ingest | 16 documents, 3 projects |
| build-indexes | 3 projects, 16 sources |
| validate | 84 Markdown files |
| build-portfolio | 3 projects → `overview`, `dependency-report`, `capability-report`, `maturity-matrix`, `documentation-coverage`, `stale-knowledge` |

Generated compiled artifacts under `generated/indexes/`: `claims.json`,
`concepts.json`, `authority.json`, `provenance.json`, `conflicts.json`.

## 2. Start the real LIVE_API

```bash
atlas live api-serve --vault .tmp/live-vault --host 127.0.0.1 --port 8765
```

`/v1/meta` reports `live_api=true`, `ask_atlas_live=true`, `mission_live=true`,
`workspace_live=true`, `cors_origin=http://127.0.0.1:5173`.

Endpoint probe (implemented routes only — no invented success routes):

| Endpoint | LIVE | Populated | Notes |
| --- | --- | --- | --- |
| `/health`, `/v1/health` | yes | yes | read_status with 3 projects |
| `/v1/projects` | yes | **yes (3)** | harbor-api / harbor-ops / harbor-portal |
| `/v1/mission` | yes | **yes** | `data_source=live_api`, `project_count=3`, board available |
| `/v1/workspace` | yes | yes | `data_source=live_api`, `empty_knowledge=true` |
| `/v1/ask?q=harbor-api` | yes | **yes** | real project match (`live_ask=true`) |
| `/v1/ask?q=<gibberish>` | yes | empty | honest UNKNOWN — no fabrication |
| `/v1/ops/receipts` | yes | empty | `available=false` (honest — no receipts) |
| `/v1/graph` | yes | empty | `available=false` → UNKNOWN (impact-graph not built by base pipeline) |
| `/v1/knowledge` | yes | empty | reads `generated/answers/` (query-persisted, not pipeline) |
| `/v1/snapshot` | yes | yes | composite read_status + graph summary |

## 3. Connect the Web to LIVE_API

```bash
cd apps/web
# default VITE_ATLAS_API_BASE = http://127.0.0.1:8765 (matches api-serve)
# Do NOT set VITE_ATLAS_DEMO_ONLY for LIVE acceptance.
npm run dev -- --host
```

**Open the app at `http://127.0.0.1:5173` (NOT `localhost`).** The API's CORS
allow-origin is exactly `http://127.0.0.1:5173`; a `localhost` origin is
CORS-blocked and the Web falls back to the isolated DEMO stub.

## 4. Verified visible journey (`http://127.0.0.1:5173`)

| # | Route | Observed (LIVE) |
| --- | --- | --- |
| A Hub | `#/` | `data_source=live_api`; "LIVE_API — read-only vault projection"; 3 harbor projects |
| B Projects | `#/projects` | harbor-api / harbor-ops / harbor-portal (no `demo-alpha`); LIVE_API banner |
| C Mission | `#/mission-control` | `lens_mode=live`, `data_source=live_api`, project_count=3, board available |
| D Knowledge | `#/knowledge` | `data_source=live_api`; honest "unknown — no knowledge rows" (never invented) |
| E Ask (known) | API `/v1/ask` | `harbor` → 3 real project matches |
| F Ask (unknown) | API `/v1/ask` | gibberish → empty (UNKNOWN, no fabrication) |
| G Conflict | vault | `conflicts.json` present (empty ids on this corpus — honest) |
| H Evidence | vault | `provenance.json` present (source provenance) |
| I Graph | `#/graph` | `data_source=live_api`, `graph_authority=false`, available=false (honest absent) |
| J Ops | `#/ops` | `data_source=live_api`, health rollup `unknown` — "unknown != healthy" |
| K Mission/Workspace | API | both LIVE (`data_source=live_api`) |
| L Doctor | CLI | `atlas doctor` reports environment + vault checks (objective; unknown != healthy) |

Invariants held throughout: `ui_canonical=false`, `graph_authority=false`,
`unknown != healthy`, LLM/derived output never elevated to authority,
`AUTHENTIC_PILOT=false`.

## 5. LIVE-UX findings

- **LIVE-UX-FINDING-001** — SEVERITY: medium · ROUTE: all read-status pages ·
  USER_ACTION: open Web at `http://localhost:5173` · EXPECTED: LIVE when API is
  running · OBSERVED: silent fallback to DEMO stub · ROOT_CAUSE: API CORS
  allow-origin is fixed to `http://127.0.0.1:5173`; `localhost` origin differs ·
  REMEDIATION: **fixed on the Web side** — the Hub now shows an explicit
  "LIVE_API not reachable — showing isolated DEMO stub … open at 127.0.0.1"
  banner (no silent stub-as-LIVE). API CORS itself is a security-owned surface
  and was not modified. · STATUS: MITIGATED (Web), API note deferred.
- **LIVE-UX-FINDING-002** — SEVERITY: low · ROUTE: `#/knowledge`, `#/graph` ·
  EXPECTED: populated knowledge/graph · OBSERVED: honest empty/absent because
  the base pipeline does not persist `generated/answers/` or build
  `generated/indexes/impact-graph.json` · ROOT_CAUSE: those artifacts come from
  query-persistence / graph-store steps not part of `discover→…→validate` ·
  REMEDIATION: none taken (would require backend/pipeline work out of scope);
  UI already reports UNKNOWN honestly. · STATUS: OPEN (documented, honest).

## Scope boundaries

- `LIVE_DEMO_FIXTURE_EXPERIENCE = PASS` (this package).
- `AUTHENTIC_PILOT`, `RELEASE_CERTIFIED`, `DESIGN_PARTNER_ALPHA_READY`,
  and `ATLAS_SECURITY_ALPHA_GATE` are **unchanged** and governed independently.
