# Atlas 2.1 — DAG (first waves)

```text
AS-2.1-DOC-REALITY-001
        |
        +--> AS-2.1-APP-SVC-001 <---+
        |            |              |
        |            +--> AS-2.1-API-SERVER-001 --> AS-2.1-WEB-LIVE-001
        |            |
        |            +--> AS-2.1-MCP-SERVER-001 (read-first)
        |
        +--> AS-2.1-AUTHZ-001 --------+
        |                             |
        +--> AS-2.1-OAI-IMPORT-REAL-001 (uses PROV quarantine; AUTHZ for promote)
        |
        +--> AS-2.1-SCHED-LIVE-001 (supervised; AUTHZ + receipts)
        |
        +--> AS-2.1-PILOT-AUTH-001-PREP --> AS-2.1-PILOT-AUTH-001
                                              |
                                              +--> SYNC/TWIN authentic deepen
                                              +--> L3_BOUNDED_AUTONOMY
                                              +--> AS-REL2.1 / v2.1.0 RC
```

## Overlap gates

| Surface | Sole-writer / integrator |
|---|---|
| `docs/atlas-2.1/**` | DOC-REALITY |
| `src/project_atlas/app_service/**` | APP-SVC (+ API/MCP consumers) |
| `src/project_atlas/api_server/**` | API-SERVER |
| `apps/web/**` live data wiring | WEB-LIVE |
| `src/project_atlas/mcp_server/**` | MCP-SERVER |
| `src/project_atlas/authz/**` | AUTHZ integrator |
| schemas touching shared kinds | schema integrator after APP-SVC |
