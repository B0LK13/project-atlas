# AS-CODER-ALPHA-OPS-EVENTS-READ-001

Vault-scoped read of the existing AS-OBS-002 operational event stream.

```
atlas ops-events --vault <dir> [--json] [--limit N]
GET /v1/ops/events?limit=
MCP  atlas.ops.events.read
Web  #/ops-events
```

- Consumes `generated/ops/events/stream.jsonl` via `ops_events.read_events`.
- Never emits, retains, or records health transitions.
- Missing stream → `UNKNOWN` (not HEALTHY, not fabricated events).
- Empty stream → `EMPTY` (not HEALTHY).
- Recorded events remain `truth_plane=operational` / `authority_plane=none`.
- OPS EVENT STREAM != AUTHORITY.
- No Layer B writes. No owner-capability grant. No AUTHENTIC_PILOT claim.

Does not replace `atlas ops events` (which can mutate), `#492` ops-receipts MCP,
or D-149 `#483`.
