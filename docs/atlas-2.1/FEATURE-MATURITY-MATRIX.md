# Atlas 2.1 — Feature maturity matrix

Tip: `1ac7a3f` (`v2.0.0`). Classes per `CHARTER.md`.

| Capability / package | Maturity | Evidence (code) | 2.1 disposition |
|---|---|---|---|
| Core CLI pipeline (discover→validate) | LIVE_PRODUCTION | `cli.py`, ingestion/validation modules; CI smoke | Keep; consume |
| `project_atlas.web_api` read adapters | LIVE_READ_ONLY (library) | `web_api/*` vault file readers | Promote via APP-SVC/API |
| `apps/web` production shell | PROTOTYPE + STUB data | sample-read-status fetch; page copy cites fixtures | AS-2.1-WEB-LIVE-001 |
| AS-2.0-API-001 surface registry | CONTRACT_ONLY | `api_surface_registry.py` | Supersede runtime by API-SERVER |
| AS-2.0-MCP-001 tool registry | CONTRACT_ONLY / DISABLED writes | `mcp_registry.py` “no live server” | AS-2.1-MCP-SERVER-001 |
| AS-2.0-WEB-ASK / WEB-SURFACE | CONTRACT_ONLY | `web_ask_atlas.py`, `web_surface_catalog.py` | Feed live API contracts |
| AS-2.0-OAI-IMPORT-001 | FIXTURE_ONLY | `openai_importer_fixtures.py` | AS-2.1-OAI-IMPORT-REAL-001 |
| AS-2.0-OAI path deepen | CONTRACT_ONLY | `openai_import_path.py` | Consume in REAL import |
| AS-2.0-PROV-001 | DISABLED / quarantine | `provider_adapters.py` no SDK | Keep quarantine; optional live later |
| AS-2.0-SCHED-001 | DRY_RUN | `scheduler_dry_run.py` forbids live | AS-2.1-SCHED-LIVE-001 |
| AS-2.0-AUTONOMY-001 | CONTRACT_ONLY / DISABLED L3+ | `autonomy_levels.py` live=false | Wave-2 L3 bounded |
| AS-2.0-SYNC-001 production | FIXTURE_ONLY (waived) | `sync_production.py` evidence_class=fixture | Needs authentic PILOT |
| AS-2.0-TWIN-001 production | FIXTURE_ONLY (waived) | `twin_production.py` estate_pilot_passed=false | Needs authentic PILOT |
| AS-2.0-TWIN-FIXTURE / AGENT-EVAL | FIXTURE_ONLY | twin/agent_eval modules | Keep as harnesses |
| AS-2.0-COMPAT / KF2 / FED | LIVE_READ_ONLY / CONTRACT | fabric + federation inventories | Keep derived |
| AS-2.0-KCI / CTX / RET-HYBRID | CONTRACT_ONLY / BOUNDED | thin compile/context/hybrid plans | Keep; deepen later |
| AS-2.0-TEMPORAL / REALITY-GAP | LIVE_READ_ONLY / FIXTURE | bitemporal + gap fixtures | Keep |
| AS-2.0-AGENTOS | CONTRACT_ONLY | session envelope | Bound to AUTHZ |
| AS-2.0-OBS-UX / AUTONOMY UI catalogs | CONTRACT_ONLY | obsidian_ux, autonomy | Docs≠plugin |
| AS-2.0-INBOX / SEC-CONT / SEC-ADV | CONTRACT_ONLY / FIXTURE | inbox + security matrices | Keep gates |
| AS-2.0-COLLAB / SCALE | STUB / FIXTURE | collaboration_stubs, scale_harness | Later |
| AS-2.0-CHATGPT / ESTATE-INTEL | FIXTURE_ONLY | chatgpt_capture, estate_intel_fixture | Optional deepen |
| docs/atlas-2.0 prototypes | PROTOTYPE / DOCUMENTATION_ONLY | `docs/atlas-2.0/prototypes/*` | Non-blocking |
| Final-cert pilot waiver (2.0) | DOCUMENTATION_ONLY / BOUNDED pin | `final_cert_pilot.py` authentic=false | Immutable 2.0; not 2.1 PILOT |
| AuthZ / RBAC | MISSING | no authz module on tip | AS-2.1-AUTHZ-001 |
| Shared application service | MISSING | web_api is library-only | AS-2.1-APP-SVC-001 |
| HTTP API server | MISSING | no FastAPI/Starlette/Flask app | AS-2.1-API-SERVER-001 |
| Authentic estate PILOT | FAIL / absent | PILOT_ROOTS historically 0 | AS-2.1-PILOT-AUTH-001-PREP |

## Matrix highlights

1. **Certified ≠ live**: 2.0 RELEASE CERTIFIED does not imply LIVE_API/WEB_DATA/MCP_READ.
2. **Biggest productionization deltas**: HTTP bridge, web live data, MCP server, real OAI export, supervised scheduler, AUTHZ, authentic PILOT.
3. **Safe to keep as-is**: Core CLI, compat anchor, derived KF2/FED/graph, fixture harnesses used as regression oracles.
4. **Do not relabel**: SYNC/TWIN fixture-waived production must not be called authentic estate.
