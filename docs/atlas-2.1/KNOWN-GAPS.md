# Atlas 2.1 — Known gaps A–K (revalidated at tip `1ac7a3f`)

| Gap | Description | Tip status | Package if still open |
|---|---|---|---|
| A | No shared application service layer above vault readers | **OPEN** | AS-2.1-APP-SVC-001 |
| B | No live HTTP API server (registry only) | **OPEN** | AS-2.1-API-SERVER-001 |
| C | Web shell uses sample JSON, not live vault data | **OPEN** | AS-2.1-WEB-LIVE-001 |
| D | MCP registry without live read server | **OPEN** | AS-2.1-MCP-SERVER-001 |
| E | OpenAI import fixture-only / no real export path | **OPEN** | AS-2.1-OAI-IMPORT-REAL-001 |
| F | Scheduler dry-run only; live dispatch forbidden | **OPEN** | AS-2.1-SCHED-LIVE-001 |
| G | No authorization / operator capability model | **OPEN** | AS-2.1-AUTHZ-001 |
| H | Autonomy L3 disabled; live_autonomy=false | **OPEN** (wave-2) | AS-2.1-AUTONOMY-L3-001 (later) |
| I | Authentic estate PILOT not PASS | **OPEN** (release-critical) | AS-2.1-PILOT-AUTH-001-PREP → PILOT |
| J | Docs/contracts overstate “production” vs runtime | **OPEN** (this audit) | AS-2.1-DOC-REALITY-001 |
| K | SYNC/TWIN production still fixture-evidence only | **OPEN** (blocked on I) | post-PILOT deepen |

All gaps A–K remain open at `v2.0.0` tip; packages created accordingly.
