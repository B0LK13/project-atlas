# AS-2.1-OAI-RESPONSES-POC-001

EXPERIMENTAL · NON_RELEASE_BLOCKING · not a substitute for authentic estate PILOT.

## Invariants

- `llm_authority=false`
- Quarantine-first via `quarantine_provider_output`
- Read-only AppService tools only (`atlas_health_read`, `atlas_projects_list`, `atlas_knowledge_list`, `atlas_graph_summary`)
- No write / promote / Layer B tools
- `OPENAI_API_KEY` from environment only (never logged)
- Offline-first: without key → `IMPLEMENTATION_READY_FOR_LIVE_SMOKE`
- With key → optional live smoke → `LIVE_SMOKE_EXECUTED`

## CLI

```bash
atlas live oai-responses-poc --vault <vault> --run-id poc-1 \
  --prompt "Summarize vault health with read-only tools" [--force-offline] [--json]
```

## Authz

Requires capability `oai.responses` (included in default operator profile).
