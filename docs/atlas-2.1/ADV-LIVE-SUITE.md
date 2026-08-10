# AS-2.1 ADV live suite (non-pilot)

Adversarial / fail-closed checks for live 2.1 surfaces. **Does not** unlock
authentic PILOT, SYNC-AUTH, TWIN-AUTH, or release certification.

| ID | Surface | Assertion |
|---|---|---|
| ADV-2.1-01 | PILOT prep | Fixture/tmp markers never count as authentic |
| ADV-2.1-02 | API | Non-local bind rejected |
| ADV-2.1-03 | API | Oversized POST → 413 |
| ADV-2.1-04 | MCP | Write tools inventory empty |
| ADV-2.1-05 | OAI POC | Unknown/write tool names rejected |
| ADV-2.1-06 | OAI POC | Offline / rate-limit statuses honest; llm_authority=false |
| ADV-2.1-07 | AUTHZ | vault.write denied by default; audit receipt reconstructable |
| ADV-2.1-08 | SCHED | Dispatch without arm fails closed |
| ADV-2.1-09 | ASK | Empty/oversized query fails closed |
| ADV-2.1-10 | SCHED | Timeout fields present on dispatch receipt |
| ADV-2.1-11 | L3 | Disable receipt reconstructable |
| ADV-2.1-12 | CHATGPT | JSON / Human-AI export variants parse |
| ADV-2.1-13 | WEB | Demo stub stamped `demo_isolated` / `data_source=demo_stub` |
| ADV-2.1-14 | PERF | Baseline receipt non-release-blocking |
| ADV-2.1-15 | COLLAB | Closed session rejects further actions |
| ADV-2.1-16 | PROVIDER | Empty/secret prompts fail closed; output quarantined |
| ADV-2.1-17 | API | Non-local Host header rejected |
| ADV-2.1-18 | MCP | projects.list.read allow-listed; write tools empty |
| ADV-2.1-19 | WEB-ACTIONS | Recent list read-only; invalid limit fails closed |
| ADV-2.1-20 | API Host/CORS | OPTIONS CORS origin; evil Host→403; local Host:port OK |
| ADV-2.1-21 | OPS receipts | Empty inventory honest unknown; no completion claim |
| ADV-2.1-22 | L3 job-matrix | Allowed jobs run; forbidden/disabled fail closed |
| ADV-2.1-23 | MCP ADV | AS-2.1-MCP-ADV-001: unknown/escalation/write-via-read/path/malformed/replay |

Executable coverage includes `tests/unit/test_as_2_1_track_b_deepen_007.py`,
`tests/unit/test_as_2_1_adv_host_cors_001.py`,
`tests/unit/test_as_2_1_mcp_adv_001.py`.
