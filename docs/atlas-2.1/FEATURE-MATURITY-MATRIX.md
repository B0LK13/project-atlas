# Atlas 2.1 — Feature maturity matrix

Tip baseline for Track B deepen-003: `044322e` (+ deepen-003 PR). Classes per `CHARTER.md`.

| Capability / package | Maturity | Evidence (code) | 2.1 disposition |
|---|---|---|---|
| Core CLI pipeline | LIVE_PRODUCTION | `cli.py` | Keep |
| AS-2.1-APP-SVC-001 | LIVE_READ_ONLY | `app_service.py` | Landed #143 |
| AS-2.1-API-SERVER-001 | LIVE_PRODUCTION (local bind) | `api_server.py` Host/obs/authz/limits | Deepening |
| AS-2.1-WEB-LIVE-001 | LIVE_READ_ONLY + isolated demo | `useReadStatus` + `useLiveKnowledge` | Deepening |
| AS-2.1-MCP-SERVER-001 | LIVE_READ_ONLY | `mcp_server.py` + projects.list | Deepening |
| AS-2.1-OAI-IMPORT-REAL-001 | BOUNDED | `openai_import_real.py` | Landed #143 |
| AS-2.1-OAI-RESPONSES-POC-001 | EXPERIMENTAL | `openai_responses_poc.py` | Non-release-blocking |
| AS-2.1-SCHED-LIVE-001 | BOUNDED + timeouts | `scheduler_live.py` | MERGED #149 |
| AS-2.1-AUTHZ-001 | LIVE_PRODUCTION (local) | `authz.py` | MERGED #146 |
| AS-2.1-AUTONOMY-L3-001 | BOUNDED + disable receipt | `autonomy_l3.py` | MERGED #149 |
| AS-2.1-CHATGPT-BRIDGE-001 | BOUNDED + export variants | `chatgpt_bridge.py` | MERGED #149 |
| AS-2.1-COLLAB-001 | BOUNDED + close | `collab_live.py` | MERGED #150 |
| AS-2.1-WEB-ACTIONS-001 | BOUNDED + recent/cap | `web_actions.py` | Deepening |
| AS-2.1-PROV-LIVE-001 | BOUNDED | `provider_live.py` | MERGED #150 |
| AS-2.1-ASK-ATLAS-LIVE-001 | LIVE_READ_ONLY | `ask_atlas_live.py` | MERGED #149 |
| AS-2.1-OBS-LIVE-001 | LIVE_READ_ONLY | `obs_live.py` + `/v1/obs` | Deepening |
| AS-2.1-PERF-BASELINE-001 | CONTRACT / local | `perf_baselines.py` + mcp timing | Deepening |
| AS-2.1-ADV-LIVE-001 | FIXTURE/ADV | ADV suite docs + unit tests | Continuing |
| Web Graph/Mission/Workspace pages | PROTOTYPE / flags-only | production pages | Remaining queue |
| Authentic estate PILOT | OWNER_BLOCKED | prep FOUND=0 | wake AUTHENTIC_ESTATE_ROOT_AVAILABLE |

## Matrix highlights

1. Track B deepen continues; board is not empty.
2. Knowledge/Projects production pages label LIVE vs DEMO explicitly.
3. OAI Responses POC remains experimental / non-release-blocking.
4. Graph/Mission/Workspace lenses remain flags-only stubs (queued).
5. Authentic PILOT remains the release gate.
