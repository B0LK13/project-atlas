# AS-OBS-003 — Ops-report / dashboard-source projection (tip-safe)

Tip-safe **regenerable ops-report** projection from the AS-OBS-001 health
snapshot, with optional read-only consume of AS-OBS-002 events when present.

Package ID: `AS-OBS-003`.

## What this is

Library helpers in `project_atlas.ops_report` plus schema `ops-report`.
Reports are written under:

```text
generated/ops/ops-report.json
generated/ops/ops-report.md
generated/ops/archive/ops-report-NNNN.{json,md}   # optional last-N
```

Reports are **operational metadata only**. They are **not**:

- project authority / temporal current / claim or query answers
- a rewrite of AS-OBS-001 health collectors or AS-OBS-002 event writers
- an event-enriched SURF / human dashboard UI (deferred band)
- a monitoring stack (Prometheus / Grafana / Datadog / paging)
- an AS-REL-001 release plane

```text
HEALTH ≠ TRUTH
HEALTH ≠ AUTHORITY
OPS REPORT ≠ PROJECT AUTHORITY
OPERATIONAL METRIC ≠ PROJECT AUTHORITY
```

## Consume rules

| Input | Mode |
|---|---|
| `generated/ops/health-snapshot.json` | **READ** (hard; missing → `unknown` report, never invent healthy) |
| `generated/ops/events/stream.jsonl` | **READ** optional (absent → empty events panel; no fabricate) |

## CLI

```bash
atlas ops report --vault <vault> [--json]
atlas ops report --vault <vault> --no-events
atlas ops report --vault <vault> --archive [--max-archive N]
atlas ops report --vault <vault> --no-write --json
```

## Fail-closed rules

- Missing / invalid OBS-001 snapshot → `snapshot_status` missing/invalid and
  estate rollup `unknown` (never fabricated `healthy`)
- Writes confined to `generated/ops/ops-report.*` (+ optional archive)
- No wall-clock `generated.at` stamps (NFR-001)
- No dual-own of `ops_health` / `ops_events` / INCR compile-cache / SURF UI
- Monitoring stacks FORBIDDEN
- Event-enriched dashboard / SURF UI band **DEFERRED** under this tip-safe freeze

## Tests

```bash
python -m pytest tests/unit/test_as_obs_003_*.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — GOVERNOR REQUIRED
AS-REL-001 MUST NOT OPEN
NO SELF-MERGE
MONITORING FORBIDDEN
EVENT_ENRICHED / SURF UI: DEFERRED
```
