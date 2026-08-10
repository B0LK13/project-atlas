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

Executable coverage: `tests/unit/test_as_2_1_pilot_oai_poc_001.py`,
`tests/unit/test_as_2_1_adv_live_001.py`,
`tests/unit/test_as_2_1_track_b_deepen_001.py`,
`tests/unit/test_as_2_1_track_b_deepen_002.py`,
`tests/unit/test_as_2_1_track_b_deepen_003.py`.
