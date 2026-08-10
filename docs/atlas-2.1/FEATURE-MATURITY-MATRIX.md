# Atlas 2.1 — Feature maturity matrix

Tip baseline for pilot+OAI-POC update: `d9b6732` (+ hardening PR). Classes per `CHARTER.md`.

| Capability / package | Maturity | Evidence (code) | 2.1 disposition |
|---|---|---|---|
| Core CLI pipeline | LIVE_PRODUCTION | `cli.py` | Keep |
| AS-2.1-APP-SVC-001 | LIVE_READ_ONLY | `app_service.py` | Landed #143 |
| AS-2.1-API-SERVER-001 | LIVE_PRODUCTION (local bind) | `api_server.py` + ask/actions/ledger/MCP list | Deepened |
| AS-2.1-WEB-LIVE-001 | LIVE_READ_ONLY + stub fallback | `apps/web/.../useReadStatus.ts` | Landed #143 |
| AS-2.1-MCP-SERVER-001 | LIVE_READ_ONLY | `mcp_server.py` + list | Deepened |
| AS-2.1-OAI-IMPORT-REAL-001 | BOUNDED | `openai_import_real.py` | Landed #143 |
| AS-2.1-OAI-RESPONSES-POC-001 | EXPERIMENTAL | `openai_responses_poc.py` | Non-release-blocking |
| AS-2.1-SCHED-LIVE-001 | BOUNDED | `scheduler_live.py` | Landed #143 |
| AS-2.1-AUTHZ-001 | LIVE_PRODUCTION (local) | `authz.py` + audit receipt | Deepened |
| AS-2.1-AUTONOMY-L3-001 | BOUNDED | `autonomy_l3.py` | Landed #144 |
| AS-2.1-CHATGPT-BRIDGE-001 | BOUNDED | `chatgpt_bridge.py` | MERGED #145 |
| AS-2.1-COLLAB-001 | BOUNDED | `collab_live.py` | MERGED #145 |
| AS-2.1-WEB-ACTIONS-001 | BOUNDED | `web_actions.py` | MERGED #145 |
| AS-2.1-PROV-LIVE-001 | BOUNDED | `provider_live.py` local-model→quarantine | MERGED #145 |
| AS-2.1-ASK-ATLAS-LIVE-001 | LIVE_READ_ONLY | `ask_atlas_live.py` | MERGED #145 |
| AS-2.1-OBS-LIVE-001 | LIVE_READ_ONLY | `obs_live.py` | MERGED #145 |
| AS-2.0 registries / fixtures | CONTRACT/FIXTURE/DRY_RUN | prior 2.0 modules | Keep as oracles |
| AS-2.0-SYNC/TWIN production | FIXTURE_ONLY (waived) | sync/twin_production | BLOCKED on authentic PILOT |
| Authentic estate PILOT | OWNER_BLOCKED | expanded prep FOUND=0 | wake AUTHENTIC_ESTATE_ROOT_AVAILABLE |

## Matrix highlights

1. Wave-1/2 live surfaces MERGED; hardening continues (API/MCP/AUTHZ/ADV).
2. OAI Responses POC is experimental and never a release substitute for authentic PILOT.
3. LLM paths quarantine only — LLM≠authority.
4. Web actions are reconstructable receipts — UI≠truth / no Layer B writes.
5. Do not relabel 2.0 fixture waiver as 2.1 PILOT PASS.
