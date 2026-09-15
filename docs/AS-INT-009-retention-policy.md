# AS-INT-009 — Raw-package and receipt retention policy

**Status:** implemented  
**Backlog:** INT-009  
**Package:** AS-INT-009

## Scope

Deterministic retention for Core-ingested agent-event raw packages and paired
receipts:

```text
sources/agent-events/<project-id>/<event-id>/
receipts/agent-events/<project-id>/<event-id>.yaml
```

Caps are **count and/or total bytes only**. There is no wall-clock freshness
predicate (NFR-001). Units are sorted lexicographically by
`project_id/event_id`; excess units are dropped from the front of that order
(keep the lexicographic tail), matching the AS-OBS-002 stream retention
pattern.

## Policy file

Optional vault policy at `.atlas/retention-policy.json`:

```json
{
  "schema_version": 1,
  "schema": "atlas.event_retention.policy.v1",
  "truth_plane": "operational",
  "authority_plane": "none",
  "note": "RAW PACKAGE / RECEIPT RETENTION ≠ PROJECT AUTHORITY",
  "max_packages": 10000,
  "max_bytes": 268435456,
  "generated": { "by": "atlas-int-009" }
}
```

Malformed policy fails closed. Missing policy → no automatic deletion
(`skipped-no-policy`). Explicit CLI caps synthesize a policy for one apply.

## Apply

```bash
atlas retention apply --vault <vault> [--max-packages N] [--max-bytes N] [--dry-run] [--json]
```

Report path: `generated/ops/retention-report.json` (`sort_keys=True`, no
`generated.at`).

When a policy file is present, `atlas ingest` invokes a thin post-promote
hook (`maybe_apply_after_ingest`). Missing policy leaves ingest unchanged.

## Explicit non-goals

- No rewrite of `recover_promote_orphans` / `_promote`
- No Layer B concept-note deletion
- No projection tombstones (AS-INT-010)
- No receipt revocation semantics (AS-INT-011)
- No `apps/web`, PILOT invent, or REL-001
