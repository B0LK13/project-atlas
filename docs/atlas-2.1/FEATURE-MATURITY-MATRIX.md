# Atlas 2.1 — Feature maturity matrix

Tip baseline for Track B deepen: `5fcaba3` (+ deepen-002). Classes per `CHARTER.md`.

| Capability / package | Maturity | Evidence (code) | 2.1 disposition |
|---|---|---|---|
| Core CLI pipeline | LIVE_PRODUCTION | `cli.py` | Keep |
| AS-2.1-APP-SVC-001 | LIVE_READ_ONLY | `app_service.py` | Landed #143 |
| AS-2.1-API-SERVER-001 | LIVE_PRODUCTION (local bind) | `api_server.py` | Deepened #146 |
| AS-2.1-WEB-LIVE-001 | LIVE_READ_ONLY + isolated demo | `useReadStatus.ts` + demo stamp | Deepening |
| AS-2.1-MCP-SERVER-001 | LIVE_READ_ONLY | `mcp_server.py` | Deepened #146 |
| AS-2.1-OAI-IMPORT-REAL-001 | BOUNDED | `openai_import_real.py` | Landed #143 |
| AS-2.1-OAI-RESPONSES-POC-001 | EXPERIMENTAL | `openai_responses_poc.py` | Non-release-blocking |
| AS-2.1-SCHED-LIVE-001 | BOUNDED + timeouts | `scheduler_live.py` | Deepening |
| AS-2.1-AUTHZ-001 | LIVE_PRODUCTION (local) | `authz.py` | Deepened #146 |
| AS-2.1-AUTONOMY-L3-001 | BOUNDED + disable receipt | `autonomy_l3.py` | Deepening |
| AS-2.1-CHATGPT-BRIDGE-001 | BOUNDED + export variants | `chatgpt_bridge.py` + parser | Deepening |
| AS-2.1-COLLAB-001 | BOUNDED | `collab_live.py` | MERGED #145 |
| AS-2.1-WEB-ACTIONS-001 | BOUNDED | `web_actions.py` | MERGED #145 |
| AS-2.1-PROV-LIVE-001 | BOUNDED | `provider_live.py` | MERGED #145 |
| AS-2.1-ASK-ATLAS-LIVE-001 | LIVE_READ_ONLY | `ask_atlas_live.py` | Deepening |
| AS-2.1-OBS-LIVE-001 | LIVE_READ_ONLY | `obs_live.py` | Deepening |
| AS-2.1-PERF-BASELINE-001 | CONTRACT / local | `perf_baselines.py` | Non-release-blocking |
| AS-2.1-ADV-LIVE-001 | FIXTURE/ADV | `docs/atlas-2.1/ADV-LIVE-SUITE.md` | MERGED #147 |
| Authentic estate PILOT | OWNER_BLOCKED | expanded prep FOUND=0 | wake AUTHENTIC_ESTATE_ROOT_AVAILABLE |

## Matrix highlights

1. Track B deepen continues while authentic PILOT remains OWNER_BLOCKED.
2. Demo stub is explicitly isolated — never relabelled as LIVE vault data.
3. OAI Responses POC remains experimental / non-release-blocking.
4. Perf baselines are reconstructable local timings — not a release substitute.
5. Do not declare board empty while deepen work remains.
