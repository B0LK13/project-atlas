# AS-DEMO-2.1-001 — API / MCP E2E script outline

| Field | Value |
|---|---|
| Package | **AS-DEMO-2.1-001** (worker **D06**) |
| Surface | LIVE_API + MCP_READ against **DEMO_FIXTURE** vault only |
| Mode | **TECHNICAL DEMO — VERIFIED** candidate steps |
| Release | **NOT RELEASE CERTIFIED** |
| Pilot | **NOT AUTHENTIC PILOT PASS** · PILOT remains **DORMANT** |
| Mutation | **No production mutation** · no authentic estate · no Layer B writes |

## Honest banner (print before any call)

```
TECHNICAL DEMO — VERIFIED candidate (API/MCP E2E outline)
DEMO_FIXTURE vault only — NOT AUTHENTIC PILOT
NOT RELEASE CERTIFIED — NOT PRODUCTION MUTATION
LIVE_API READ + MCP_READ != AUTHORITY / != ESTATE SCAN
```

Operators must not treat a green checklist as Atlas 2.1 release evidence or authentic-pilot PASS.

## Scope

This document is an **operator runbook outline** (manual or scripted), not a CI gate and not release certification.

**In scope**

- `GET /v1/meta` — package / truth-boundary / feature flags
- `GET /v1/ops/receipts` — honest ops receipt inventory (UNKNOWN ≠ healthy)
- MCP_READ allow-listed tools via `atlas live mcp-invoke` (and optional `GET /v1/mcp/tools`)

**Out of scope / forbidden in this demo lane**

- Authentic estate roots / PILOT wake
- Production vault mutation, Layer B concept writes, vault-write / estate-scan MCP tools
- Claiming RELEASE CERTIFIED, PILOT PASS, or authority from receipt presence
- Binding non-local API hosts (`api-bind-non-local-forbidden`)

## Prerequisites

1. Checkout tip that includes `api_server.py`, `ops_receipts.py`, `mcp_server.py` (post AS-2.1 API/MCP landings).
2. Editable install: `pip install -e ".[dev]"`.
3. **DEMO_FIXTURE vault only** — prefer paths under:
   - `docs/demo/fixtures/` (D03 story pack when present), or
   - `fixtures/demo/` (hero fixture when present), or
   - a local throwaway vault initialized for demo (`atlas init --output <demo-vault>`), labeled DEMO in notes.
4. Never point `--vault` at an authentic project estate or production Obsidian vault.
5. Default bind: `127.0.0.1:8765` (localhost Host gate + CORS for `http://127.0.0.1:5173`).

Companion checklist: [`checklists/api-mcp.md`](checklists/api-mcp.md).

## Phase 0 — Refuse production mutation

Before serving:

| Check | Pass criterion |
|---|---|
| Vault path | Under demo/fixture tree; path string contains `demo` or is explicitly labeled DEMO_FIXTURE |
| Write tools | MCP `atlas.vault.write` / `atlas.estate.scan` remain **disabled** / denied |
| API writes | Only bounded `POST /v1/actions` exists; **skip POST** in this E2E outline (read-only demo) |
| Host | Serve on `127.0.0.1` only |

If any check fails → **STOP**. Do not continue the demo.

## Phase 1 — Start LIVE_API against demo vault

```powershell
# DEMO_FIXTURE only — replace with local demo vault path
$DemoVault = "docs/demo/fixtures/poc-vault"   # or fixtures/demo/...
atlas live api-serve --vault $DemoVault --host 127.0.0.1 --port 8765
```

Expected log (stderr): LIVE_API listening on `127.0.0.1:8765`.

Keep this process running for Phases 2–3. Tear down with Ctrl+C (or companion demo-down script when present).

## Phase 2 — `/v1/meta`

```powershell
curl.exe -s http://127.0.0.1:8765/v1/meta
```

### Assert (outline)

| Field | Expected |
|---|---|
| HTTP | `200` |
| `package_id` | `AS-2.1-API-SERVER-001` |
| `write_enabled` | `false` |
| `live_api` | `true` |
| `ops_receipts` | `true` |
| `truth_boundary` | contains `!= AUTHORITY` (LIVE_API read + bounded actions ≠ Layer B) |
| Headers | `X-Atlas-Package`, `X-Atlas-Truth-Boundary` present |

### Negative probes (optional ADV flavor)

| Probe | Expected |
|---|---|
| `Host: evil.example` on `/v1/meta` | `403` `host-non-local-forbidden` |
| `PUT` / `DELETE` any path | `405` `writes-forbidden` |

## Phase 3 — `/v1/ops/receipts`

```powershell
curl.exe -s "http://127.0.0.1:8765/v1/ops/receipts?limit=50"
```

### Assert (outline)

| Field | Expected |
|---|---|
| HTTP | `200` |
| `package_id` | `AS-2.1-OPS-RECEIPT-ADAPTER` |
| `rollup` / `health` | `unknown` (presence of files **never** upgrades rollup) |
| `unknown_equals_healthy` | `false` |
| `completion_claimed` | `false` |
| `authentic_pilot` | `false` |
| `release_certified` | `false` |
| `authority` | `false` |
| Empty demo vault | `available=false`, `ops_root=absent`, `receipts=[]` still honest UNKNOWN |

Demo receipts under `generated/ops/**` (when planted by D03) must remain labeled **DEMO ≠ pilot**. Inventory metadata only — no claim promotion.

### Limit / error outline

| Call | Expected |
|---|---|
| `?limit=0` or `?limit=501` | `400` limit error |
| `?limit=2` with many rows | `truncated=true` when applicable |

## Phase 4 — MCP tools (read-only)

Prefer CLI (no extra daemon):

```powershell
# Inventory via LIVE_API (same authz surface)
curl.exe -s http://127.0.0.1:8765/v1/mcp/tools

# Invoke allow-listed read tools against DEMO vault
atlas live mcp-invoke --vault $DemoVault --tool atlas.ops.health.read --json
atlas live mcp-invoke --vault $DemoVault --tool atlas.projects.list.read --json
atlas live mcp-invoke --vault $DemoVault --tool atlas.knowledge.query.read --json
atlas live mcp-invoke --vault $DemoVault --tool atlas.explain.receipt.read --json
```

### Allow-list (enabled vault-read)

- `atlas.ops.health.read`
- `atlas.knowledge.query.read`
- `atlas.explain.receipt.read`
- `atlas.projects.list.read`

### Deny probes (must fail closed)

```powershell
atlas live mcp-invoke --vault $DemoVault --tool atlas.vault.write --json
atlas live mcp-invoke --vault $DemoVault --tool atlas.estate.scan --json
atlas live mcp-invoke --vault $DemoVault --tool atlas.provider.generate --json
atlas live mcp-invoke --vault $DemoVault --tool atlas.unknown.fabricate --json
```

Expected: non-zero exit / `mcp-tool-denied:*` (or ADV path-traversal / malformed-id errors). **No vault mutation.**

### Response shape (outline)

Successful invoke JSON includes:

- `package_id`: `AS-2.1-MCP-SERVER-001`
- `live_mcp_read`: `true`
- `truth_boundary`: MCP_READ ≠ WRITE / ≠ AUTHORITY / ≠ ESTATE SCAN
- `write_tools` empty on list endpoint

## Phase 5 — Tear down & non-claims

1. Stop `api-serve`.
2. Confirm demo vault path was never an authentic estate root.
3. Record run notes as **TECHNICAL DEMO** evidence only.

### Explicit non-claims

- Passing this outline does **not** equal **RELEASE CERTIFIED**.
- DEMO_FIXTURE success does **not** equal authentic **PILOT PASS**.
- Ops receipt rows do **not** equal completion, healthy rollup, or authority.
- MCP_READ success does **not** enable vault-write or estate-scan.

## Mapping to TECHNICAL DEMO — VERIFIED

| Criterion | This outline |
|---|---|
| Honest DEMO label | Banner + DEMO_FIXTURE vault only |
| API meta truth | `/v1/meta` `write_enabled=false` |
| Ops honesty | `/v1/ops/receipts` UNKNOWN ≠ healthy |
| MCP deny-by-default | Write/scan tools denied |
| No production mutation | Read-only phases; no authentic roots |

Certificate language (when ADV/D08 pack lands): **"TECHNICAL DEMO — VERIFIED"** with **"NOT RELEASE CERTIFIED"** / **"NOT AUTHENTIC PILOT PASS"**.

## Related packages

| Package | Role |
|---|---|
| AS-2.1-API-SERVER-001 | `serve_api` / `/v1/*` |
| AS-2.1-OPS-RECEIPT-ADAPTER | `inventory_ops_receipts` |
| AS-2.1-MCP-SERVER-001 | `invoke_mcp_tool` / `list_mcp_tools` |
| AS-2.1-MCP-ADV-001 | Fail-closed request / tool-id guards |
| AS-DEMO-2.1-001 | Demo charter / fixtures / launchers (sibling DEMO workers) |
