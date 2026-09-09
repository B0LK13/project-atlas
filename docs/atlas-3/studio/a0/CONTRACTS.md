# AS-STUDIO-A0-001 — versioned contracts

```text
STUDIO_UI != AUTHORITY
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
```

## Schemas

| Const | File | Purpose |
|---|---|---|
| `ATLAS_STUDIO_SNAPSHOT_V1` | `schemas/atlas_studio_snapshot_v1.schema.json` | Read-only Studio projection aggregate |
| `ATLAS_STUDIO_EVENT_V1` | `schemas/atlas_studio_event_v1.schema.json` | Read-only observation events (not authority) |

## Snapshot required honesty

All must be JSON `true` (schema `const`):

- `studio_ui_ne_authority`
- `ui_state_is_projection`
- `grants_no_mutation`
- `no_cli_text_parsing_as_protocol`

Additional honesty fields (also const true in A0 implementation):

- `atlas_daemon_is_authoritative_runtime`
- `studio_crash_ne_agent_task_termination`
- `model_provider_ne_atlas_architecture`
- `no_wholesale_core_rewrite`
- `reuse_before_reimplement`

## Snapshot shape (informative)

- `schema`, `generated_at_utc`, `repository`, `agent`, `agent_status`
- `slice_status`: `OK` | `DEGRADED` | `UNKNOWN`
- `snapshot_fingerprint`: sha-256 hex of canonical projection body
- `honesty` (above)
- `panels`: projections of control_view / telemetry / efficiency_metrics /
  residuals (each may be status-wrapped when unavailable)
- `observation_events`: list of `ATLAS_STUDIO_EVENT_V1` (optional empty)
- `provenance`: generator notes, truth_sources, presentation_only

## Event shape (informative)

- Observation only: `kind` constrained; `observation_ne_authority: true`
- Must never grant claim/dispatch/merge/IV

## Wire rule

Clients speak these schemas (or future `_V2`). They must not scrape CLI text.
