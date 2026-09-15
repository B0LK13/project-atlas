# AS-OBS-002 — Operator guide (Operational Event Model)

| Field | Value |
|---|---|
| Package | `AS-OBS-002` |
| Product | Append-only `OPS-EVT-*` stream under `generated/ops/events/` |
| Planes | `truth_plane: operational` · `authority_plane: none` |
| AS-OBS-001 | **CLOSED** — consume `health-snapshot.json` only |
| AS-REL-001 | **MUST NOT OPEN** |

## Commands

```bash
# List / replay stream
atlas ops events --vault <vault> [--json]

# Consume OBS-001 snapshot; append OPS-EVT-HEALTH-TRANSITION on rollup change
atlas ops events --vault <vault> --record-health-transitions [--json]

# Apply count retention (newest N; default 10000)
atlas ops events --vault <vault> --retain [--max-events N]
```

Library emitters may also call `append_event(...)` for other catalog IDs when
evidence refs exist. Missing emitters must not fabricate events.

## Paths (owned)

| Path | Role |
|---|---|
| `generated/ops/events/stream.jsonl` | Append-only event log |
| `generated/ops/events/stream-manifest.json` | Sequence / retention metadata |
| `generated/ops/events/health-state.json` | Prior estate rollup for transitions |
| `generated/ops/health-snapshot.json` | **READ** only (AS-OBS-001) |

## Invariants

- Events ≠ project authority / temporal current / query answers.
- NFR-004: no secret material in payloads.
- NFR-001: no wall-clock timestamps; retention is count/size capped.
- Retention never deletes receipts or Layer A evidence.
- Monitoring stacks / paging vendors: **FORBIDDEN**.
