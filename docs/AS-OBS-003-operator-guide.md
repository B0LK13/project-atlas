# AS-OBS-003 — Operator guide (Ops-report)

| Field | Value |
|---|---|
| Package | `AS-OBS-003` |
| Product | Regenerable `ops-report.{json,md}` under `generated/ops/` |
| Planes | `truth_plane: operational` · `authority_plane: none` |
| AS-OBS-001 | **CLOSED** — consume `health-snapshot.json` only |
| AS-OBS-002 | Optional consume of `events/stream.jsonl` (no dual-own writers) |
| AS-REL-001 | **MUST NOT OPEN** |

## Commands

```bash
# Emit ops-report (JSON + Markdown)
atlas ops report --vault <vault> [--json]

# Snapshot-only (skip optional OBS-002 events panel)
atlas ops report --vault <vault> --no-events

# Also archive last-N copies under generated/ops/archive/
atlas ops report --vault <vault> --archive [--max-archive 50]

# Project without writing
atlas ops report --vault <vault> --no-write --json
```

Typical flow:

```bash
atlas ops health --vault <vault>
atlas ops events --vault <vault> --record-health-transitions   # optional
atlas ops report --vault <vault>
```

## Paths

| Path | Role |
|---|---|
| `generated/ops/ops-report.json` | Machine report (owned WRITE) |
| `generated/ops/ops-report.md` | Human Markdown projection (owned WRITE) |
| `generated/ops/archive/ops-report-NNNN.*` | Optional last-N archive |
| `generated/ops/health-snapshot.json` | **READ** only (AS-OBS-001) |
| `generated/ops/events/**` | **READ** optional (AS-OBS-002) |

## Invariants

- Ops report ≠ project authority / temporal current / query answers.
- Missing snapshot → unknown report (never invent healthy).
- Monitoring stacks / paging vendors: **FORBIDDEN**.
- SURF / event-enriched UI: **DEFERRED**.
