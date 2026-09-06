# Atlas for ChatGPT — read-only MCP (P0)

> `ATLAS-FOR-CHATGPT-READONLY-001` · **DEMO_FIXTURE only** · **AUTHENTIC_PILOT = FALSE**
>
> Proves a ChatGPT conversation can inspect Atlas **projects, knowledge,
> evidence, graph relationships and status** through a governed **read-only**
> interface. Not write access, not canonical mutation, not a full provider
> integration, not release/pilot.

## Architecture

```
ChatGPT → Atlas ChatGPT app → Apps SDK / MCP → Atlas read-only gateway → Atlas data
                                                          │
                                        projects · knowledge · evidence · graph
```

- `atlas_gateway.py` — read-only gateway. Reuses the **current** Atlas product
  behavior (`project_atlas.web_api` + generated artifacts). It never duplicates
  Atlas truth logic, never writes, and never imports ingestion/compilation
  writers. Fully unit-tested and usable without the MCP SDK.
- `server.py` — MCP server (Apps SDK) exposing the gateway as tools **and**
  registering the widget as an MCP resource (`resources/list` +
  `resources/read`). Every tool is `readOnlyHint=true`,
  `destructiveHint=false`, `openWorldHint=false`, and links
  `ui://widget/atlas-card.html` via `_meta.ui.resourceUri`
  (+ `openai/outputTemplate` alias). **`WRITE_TOOL_COUNT = 0`**.
- `web/atlas-card.html` — adaptive Apps SDK card (project / graph / evidence /
  search) reading `window.openai.toolOutput` (MCP Apps bridge). Served as
  `text/html;profile=mcp-app` with a strict CSP (`default-src 'none'`).
  Visually separates **ATLAS EVIDENCE** from **MODEL INTERPRETATION**; shows
  `GRAPH != AUTHORITY` and `UNKNOWN != HEALTHY` without dominating the UX.

Isolation: nothing here modifies security-owned surfaces (`ingestion`,
`discovery`, `api_server`, `authz`, scheduler, autonomy, `openai_responses_poc`,
`openai_import*`, `chatgpt_bridge`, `web_actions`, Windows scripts,
control-plane). `SURFACE_OVERLAP = NO OVERLAP`.

## Tools (all READ ONLY)

| Tool | Job | Output |
| --- | --- | --- |
| `search` | locate Atlas references for a query | compact references (not proven claims) |
| `fetch` | full representation for a `<type>:<id>` ref | project / knowledge / claim / conflict / evidence / receipt |
| `atlas_project_status` | project state card | concepts, knowledge, conflicts, evidence, dependencies, unknowns |
| `atlas_graph_neighbors` | derived relationships | dependencies / dependents / related (GRAPH != AUTHORITY) |

No write/ingest/delete/execute tool is registered. `WRITE_TOOL_COUNT = 0`
(asserted in tests).

## Resources (Apps SDK widget)

| URI | MIME | File |
| --- | --- | --- |
| `ui://widget/atlas-card.html` | `text/html;profile=mcp-app` | `web/atlas-card.html` |

Clients resolve `openai/outputTemplate` / `_meta.ui.resourceUri` via
`resources/read`. CSP meta tag is required and covered by tests.

## Trust invariants (echoed on every result)

`source_class=DEMO_FIXTURE` · `authentic_pilot=false` · `ui_canonical=false` ·
`graph_authority=false` · `llm_output_authority=false` ·
`unknown_equals_healthy=false` · `search_result_is_proven_claim=false` ·
`evidence_is_interpretation=false`. ChatGPT may explain Atlas truth; it must not
silently redefine it, and must report UNKNOWN honestly (no fabrication).

## Build the DEMO_FIXTURE vault (Phase A corpus)

```bash
atlas init          --output .tmp/live-vault
atlas discover      --source tests/fixtures/demo/estate --output .tmp/live-manifest.json
atlas ingest        --manifest .tmp/live-manifest.json  --vault .tmp/live-vault --source tests/fixtures/demo/estate
atlas build-indexes --vault .tmp/live-vault
atlas build-portfolio --vault .tmp/live-vault
```

## Run the MCP server (local, no OpenAI key required)

```bash
pip install -r integrations/chatgpt-atlas/requirements.txt
ATLAS_DEMO_VAULT="$PWD/.tmp/live-vault" \
  PYTHONPATH="src:integrations/chatgpt-atlas" \
  python integrations/chatgpt-atlas/server.py       # stdio MCP transport
```

Point a ChatGPT Apps SDK / MCP client (developer mode) at this stdio server. The
widget template URI is `ui://widget/atlas-card.html` (served via MCP
`resources/read`).

## Runtime honesty — EXTERNAL_BLOCKED

Local pytest + MCP stdio prove the **code and trust invariants**. Live ChatGPT
Apps SDK / hosted connector runtime may remain **`EXTERNAL_BLOCKED`** (no
OpenAI org connector registration, developer-mode entitlement, or external
security revalidation in this package). That does **not** invent a pilot pass:

| Claim | Status |
| --- | --- |
| Code + unit/integration tests (DEMO_FIXTURE) | SHIPPED |
| `WRITE_TOOL_COUNT` | **0** |
| Live ChatGPT Apps runtime | may be **EXTERNAL_BLOCKED** |
| `AUTHENTIC_PILOT` / release cert | **FALSE / unchanged** |
| `EXTERNAL_SECURITY_REVALIDATION_REQUIRED` | **YES** |
| `CODEX_VALIDATED` | **NO** |

## Test

```bash
PYTHONPATH="src:integrations/chatgpt-atlas" \
  python -m pytest integrations/chatgpt-atlas/tests -q --no-cov
```

Covers: widget `resources/list`+`resources/read` + CSP; `WRITE_TOOL_COUNT=0`;
list projects; project status; "what depends on harbor-api?" (real derived
`harbor-portal → harbor-api` edge); conflicts + unknowns honest; unknown project
not fabricated; evidence/receipt index keys; every tool read-only.

## Scope boundaries

- Proves at most `LIVE_DEMO_FIXTURE_EXPERIENCE`/read-only ChatGPT inspection.
- Does **not** touch `openai_responses_poc.py` (CODEX-SEC-023 / -024 remain under
  the Cursor → Codex lifecycle) or any security-owned surface.
- `AUTHENTIC_PILOT`, `RELEASE_CERTIFIED`, `ATLAS_SECURITY_ALPHA_GATE` unchanged.
