# Atlas 2.1 — Package board

Tip: `70b52b0` + Track B deepen-007 (queue drain). `ATLAS_2_1_RELEASE_CERTIFIED = NO`.

| Package | Wave | Status | Notes |
|---|---|---|---|
| AS-2.1-DOC-REALITY-001 | 1 | MERGED #143 | Audit + matrix |
| AS-2.1-APP-SVC-001 | 1 | MERGED #143 | App service |
| AS-2.1-API-SERVER-001 | 1–5 | MERGED #153/#154 | Host/mission/workspace |
| AS-2.1-WEB-LIVE-001 | 1–5 | MERGED #153 + polish | Mission/Workspace/Ops |
| AS-2.1-MCP-SERVER-001 | 1–4 | MERGED #151 | projects.list.read |
| AS-2.1-OAI-IMPORT-REAL-001 | 1/5 | MERGED #153 | export size cap |
| AS-2.1-SCHED-LIVE-001 | 1/4 | MERGED #149 | timeout receipts |
| AS-2.1-AUTHZ-001 | 1–3 | MERGED #146 | caps + audit |
| AS-2.1-PILOT-AUTH-001-PREP | 1/3 | MERGED #146 | Bounded scan |
| AS-2.1-AUTONOMY-L3-001 | 2/5 | MERGED #153 + ADV | loop + job-matrix ADV |
| AS-2.1-CHATGPT-BRIDGE-001 | 2/4 | MERGED #149 | export variants |
| AS-2.1-COLLAB-001 | 2/4 | MERGED #150 | close-session |
| AS-2.1-WEB-ACTIONS-001 | 2/4 | MERGED #151 | ledger cap |
| AS-2.1-PROV-LIVE-001 | 2/4 | MERGED #150 | provider ADV |
| AS-2.1-ASK / OBS / OPS-RECEIPTS | 2–5 | LANDING | `/v1/ops/receipts` |
| AS-2.1-OAI-RESPONSES-POC-001 | 3 | MERGED #146 | NON_RELEASE_BLOCKING |
| AS-2.1-ADV-LIVE-001 | 3–5 | MERGED #147–#154 + | Host/CORS + L3 matrix |
| AS-2.1-PERF-BASELINE-001 | 4 | MERGED #151 | local baselines |
| Strategy gap pack | — | MERGED #152 | two backlogs |
| AS-2.1-PILOT-AUTH-001 | — | **OWNER_BLOCKED** | FOUND=0 |
| AS-2.1-SYNC-AUTH / TWIN-AUTH | 3 | BLOCKED on PILOT | Authentic only |
| AS-REL-2.1-001 | RC | NOT OPEN | v2.1.0 |

## Track B queue

**BOARD_EMPTY_EXCEPT_AUTHENTIC_PILOT** for release-hardening (after deepen-007 land).

Remaining non-release polish (optional, not P0 product widen):
- Further Mission/Workspace visual polish only
- RC-time ADV fan-out still required post-PILOT

**Separate north-star backlog:** `docs/strategy/` — do not merge into 2.1 P0.

Release gated on authentic PILOT PASS.
