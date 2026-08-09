# AS-OBS-002 — Operational Event Model (`OPS-EVT-*`)

Tip-safe **append-only operational event stream** for Atlas estate health
transitions and machine consumers that need a feed rather than a single
OBS-001 snapshot.

Package ID: `AS-OBS-002`.

## What this is

Library helpers in `project_atlas.ops_events` plus schemas `ops-event` and
`ops-event-stream`. Events are written under:

```text
generated/ops/events/stream.jsonl
generated/ops/events/stream-manifest.json
generated/ops/events/health-state.json   # prior estate rollup for transitions
```

Events are **operational metadata only**. They are **not**:

- project authority / temporal current / claim or query answers
- a rewrite of AS-OBS-001 health snapshot collectors
- AS-OBS-003 ops-report / dashboard projection
- a monitoring stack (Prometheus / Grafana / Datadog / paging)
- an AS-REL-001 release plane

```text
HEALTH ≠ TRUTH
HEALTH ≠ AUTHORITY
OPS-EVT-* ≠ PROJECT AUTHORITY
```

## Catalog (Wave-006 §5)

Tip-safe emitters may use any ID in the normative catalog
(`EVENT_CATALOG` in `ops_events.py`). Missing real evidence → **no fabricated
event**.

Notable tip-safe helper:

| Helper | Role |
|---|---|
| `build_event` / `append_event` | Schema-bound append under `generated/ops/events/**` |
| `read_events` | Fail-closed JSONL replay |
| `apply_retention` | Count / size caps (default 10k events / 8 MiB) |
| `record_health_transition` | Consume OBS-001 snapshot; emit `OPS-EVT-HEALTH-TRANSITION` only on from→to change |

## CLI

```bash
atlas ops events --vault <vault> [--json]
atlas ops events --vault <vault> --record-health-transitions
atlas ops events --vault <vault> --retain [--max-events N]
```

## Fail-closed rules

- Unknown `OPS-EVT-*` IDs rejected
- Empty `evidence_refs` rejected (no fabricated events)
- Secret-shaped payload text rejected (NFR-004)
- Writes confined to `generated/ops/events/**`
- No wall-clock `generated.at` stamps (NFR-001)
- First health observation seeds prior state only — **no** bootstrap transition event

## Tests

```bash
python -m pytest tests/unit/test_as_obs_002_*.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — GOVERNOR REQUIRED
AS-REL-001 MUST NOT OPEN
NO SELF-MERGE
MONITORING FORBIDDEN
```
