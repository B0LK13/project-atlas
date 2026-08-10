# Atlas 2.1 — Package board

Tip: `f98be17` + Track B deepen-004. `ATLAS_2_1_RELEASE_CERTIFIED = NO`.

| Package | Wave | Status | Notes |
|---|---|---|---|
| AS-2.1-DOC-REALITY-001 | 1 | MERGED #143 | Audit + matrix |
| AS-2.1-APP-SVC-001 | 1 | MERGED #143 | App service |
| AS-2.1-API-SERVER-001 | 1–4 | MERGED #151 | Host/obs/authz/limits |
| AS-2.1-WEB-LIVE-001 | 1–4 | DEEPENING | Graph LIVE + Ops labels |
| AS-2.1-MCP-SERVER-001 | 1–4 | MERGED #151 | projects.list.read |
| AS-2.1-OAI-IMPORT-REAL-001 | 1 | MERGED #143 | Real export |
| AS-2.1-SCHED-LIVE-001 | 1/4 | MERGED #149 | timeout receipts |
| AS-2.1-AUTHZ-001 | 1–3 | MERGED #146 | + oai.responses + audit |
| AS-2.1-PILOT-AUTH-001-PREP | 1/3 | MERGED #146 | Bounded env/workspace scan |
| AS-2.1-AUTONOMY-L3-001 | 2/4 | MERGED #149 | timeout + disable receipt |
| AS-2.1-CHATGPT-BRIDGE-001 | 2/4 | MERGED #149 | JSON/Human-AI variants |
| AS-2.1-COLLAB-001 | 2/4 | MERGED #150 | close-session receipt |
| AS-2.1-WEB-ACTIONS-001 | 2/4 | MERGED #151 | recent list + ledger cap |
| AS-2.1-PROV-LIVE-001 | 2/4 | MERGED #150 | ADV provider bounds |
| AS-2.1-ASK-ATLAS-LIVE / OBS-LIVE | 2/4 | MERGED #149/#151 | health + `/v1/obs` |
| AS-2.1-OAI-RESPONSES-POC-001 | 3 | MERGED #146 | EXPERIMENTAL non-blocking |
| AS-2.1-ADV-LIVE-001 | 3/4 | MERGED #147–#151 | ADV suites continuing |
| AS-2.1-PERF-BASELINE-001 | 4 | MERGED #151 | + mcp list timing |
| AS-2.1-PILOT-AUTH-001 | — | **OWNER_BLOCKED** | FOUND=0; wake AUTHENTIC_ESTATE_ROOT_AVAILABLE |
| AS-2.1-SYNC-AUTH / TWIN-AUTH | 3 | BLOCKED on PILOT | Authentic only |
| AS-REL-2.1-001 | RC | NOT OPEN | v2.1.0 |

## Remaining Track B queue (honest)

1. Mission / Workspace production pages still flags-only stubs
2. Ops receipt adapter still unavailable (honest unknown)
3. L3 supervised job runner loop (policy→dispatch) still thin
4. OpenAI import real export size/format ADV beyond ChatGPT bridge
5. Continuous Host/CORS ADV matrices

**Separate north-star backlog:** `docs/strategy/` (gap register + 2.2/2.3/3.0) — do not merge into 2.1 P0.

Hardening continues; board is **not** empty. Release gated on authentic PILOT PASS.
