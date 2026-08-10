# Atlas 2.1 — Feature maturity matrix

Tip baseline: `4f3ade9` / TREE `80a4ba55` (post #155). Classes per `CHARTER.md`.

| Capability / package | Maturity | Evidence (code) | 2.1 disposition |
|---|---|---|---|
| Core CLI pipeline | LIVE_PRODUCTION | `cli.py` | Keep |
| AS-2.1-APP-SVC-001 | LIVE_READ_ONLY | `app_service.py` | Landed #143 |
| AS-2.1-API-SERVER-001 | LIVE_PRODUCTION (local bind) | `api_server.py` Host/obs/authz/limits | MERGED #153/#154 |
| AS-2.1-WEB-LIVE-001 | LIVE_READ_ONLY + isolated demo | hooks + Mission/Workspace/Ops | MERGED #153/#155 |
| AS-2.1-MCP-SERVER-001 | LIVE_READ_ONLY | `mcp_server.py` + projects.list | MERGED #151 |
| AS-2.1-OAI-IMPORT-REAL-001 | BOUNDED + size cap | `openai_import_real.py` | MERGED #153 |
| AS-2.1-OAI-RESPONSES-POC-001 | EXPERIMENTAL | `openai_responses_poc.py` | Non-release-blocking |
| AS-2.1-SCHED-LIVE-001 | BOUNDED + timeouts | `scheduler_live.py` | MERGED #149 |
| AS-2.1-AUTHZ-001 | LIVE_PRODUCTION (local) | `authz.py` | MERGED #146 |
| AS-2.1-AUTONOMY-L3-001 | BOUNDED + loop + ADV | `autonomy_l3.py` | MERGED #153/#155 |
| AS-2.1-CHATGPT-BRIDGE-001 | BOUNDED + export variants | `chatgpt_bridge.py` | MERGED #149 |
| AS-2.1-COLLAB-001 | BOUNDED + close | `collab_live.py` | MERGED #150 |
| AS-2.1-WEB-ACTIONS-001 | BOUNDED + recent/cap | `web_actions.py` | MERGED #151 |
| AS-2.1-PROV-LIVE-001 | BOUNDED | `provider_live.py` | MERGED #150 |
| AS-2.1-ASK-ATLAS-LIVE-001 | LIVE_READ_ONLY | `ask_atlas_live.py` | MERGED #149 |
| AS-2.1-OBS-LIVE-001 | LIVE_READ_ONLY | `obs_live.py` + `/v1/obs` | MERGED |
| AS-2.1-OPS-RECEIPTS-001 | LIVE_READ_ONLY / honest empty | `ops_receipts.py` + `/v1/ops/receipts` | MERGED #155 |
| AS-2.1-PERF-BASELINE-001 | CONTRACT / local | `perf_baselines.py` | MERGED #151 |
| AS-2.1-ADV-LIVE-001 | FIXTURE/ADV | ADV suite + unit tests | Continuing pre-RC |
| Web Graph/Mission/Workspace | LIVE_READ_ONLY (bounded) | production pages + hooks | H01 drained |
| Authentic estate PILOT | OWNER_BLOCKED | prep FOUND=0 | wake AUTHENTIC_ESTATE_ROOT_AVAILABLE |

## Matrix highlights

1. **BOARD_EMPTY_EXCEPT_AUTHENTIC_PILOT** for release-hardening Track B.
2. Knowledge/Projects/Mission/Workspace/Ops label LIVE vs DEMO explicitly.
3. OAI Responses POC remains experimental / non-release-blocking.
4. Authentic PILOT remains the sole release gate (plus post-PILOT SYNC/TWIN/E2E/ADV-RC/REL).
5. North-star gaps stay in `docs/strategy/` — not 2.1 scope wideners.
