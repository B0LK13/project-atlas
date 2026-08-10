# Atlas 2.1 — Feature maturity matrix

Tip baseline for Wave-2 update: `4e83cde` (+ Wave-2 PR). Classes per `CHARTER.md`.

| Capability / package | Maturity | Evidence (code) | 2.1 disposition |
|---|---|---|---|
| Core CLI pipeline | LIVE_PRODUCTION | `cli.py` | Keep |
| AS-2.1-APP-SVC-001 | LIVE_READ_ONLY | `app_service.py` | Landed #143 |
| AS-2.1-API-SERVER-001 | LIVE_PRODUCTION (local bind) | `api_server.py` + `/v1/ask` + `/v1/actions` | Landed; actions bounded |
| AS-2.1-WEB-LIVE-001 | LIVE_READ_ONLY + stub fallback | `apps/web/.../useReadStatus.ts` | Landed #143 |
| AS-2.1-MCP-SERVER-001 | LIVE_READ_ONLY | `mcp_server.py` | Landed #143 |
| AS-2.1-OAI-IMPORT-REAL-001 | BOUNDED | `openai_import_real.py` | Landed #143 |
| AS-2.1-SCHED-LIVE-001 | BOUNDED | `scheduler_live.py` | Landed #143 |
| AS-2.1-AUTHZ-001 | LIVE_PRODUCTION (local) | `authz.py` | Landed; Wave-2 caps extended |
| AS-2.1-AUTONOMY-L3-001 | BOUNDED | `autonomy_l3.py` | Landed #144 |
| AS-2.1-CHATGPT-BRIDGE-001 | BOUNDED | `chatgpt_bridge.py` | Wave-2 |
| AS-2.1-COLLAB-001 | BOUNDED | `collab_live.py` | Wave-2 |
| AS-2.1-WEB-ACTIONS-001 | BOUNDED | `web_actions.py` | Wave-2 |
| AS-2.1-PROV-LIVE-001 | BOUNDED | `provider_live.py` local-model→quarantine | Wave-2 |
| AS-2.1-ASK-ATLAS-LIVE-001 | LIVE_READ_ONLY | `ask_atlas_live.py` | Wave-2 polish |
| AS-2.1-OBS-LIVE-001 | LIVE_READ_ONLY | `obs_live.py` | Wave-2 polish |
| AS-2.0 registries / fixtures | CONTRACT/FIXTURE/DRY_RUN | prior 2.0 modules | Keep as oracles |
| AS-2.0-SYNC/TWIN production | FIXTURE_ONLY (waived) | sync/twin_production | BLOCKED on authentic PILOT |
| Authentic estate PILOT | FAIL / escalate | known-root scan FOUND=0 | OWNER ASK open |

## Matrix highlights

1. Wave-1/2 live surfaces exist; authentic PILOT remains the release gate.
2. LLM paths (ChatGPT bridge, PROV live) quarantine only — LLM≠authority.
3. Web actions are reconstructable receipts — UI≠truth / no Layer B writes.
4. Do not relabel 2.0 fixture waiver as 2.1 PILOT PASS.
