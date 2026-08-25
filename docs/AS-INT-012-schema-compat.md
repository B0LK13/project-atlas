# AS-INT-012 — Schema migration and compatibility tooling

**Status:** implemented  
**Backlog:** INT-012  
**Package:** AS-INT-012

## Scope

Deterministic operational scan of known vault ops JSON artifacts against
shipped package schemas, plus a **dry-run** migration plan. Never invents
authority; never rewrites Layer B; dry-run never mutates scanned artifacts.

Report path: `generated/ops/schema-compat-report.json`.

Default scan targets:

- `generated/ops/event-tombstones.json` → `event-tombstone-index`
- `generated/ops/receipt-revocations.json` → `receipt-revocation-index`
- `generated/ops/retention-report.json` → `event-retention-report`
- `.atlas/retention-policy.json` → `event-retention-policy`

## Commands

```bash
atlas schema compat --vault <vault> [--json]
atlas schema migrate --vault <vault> [--json]   # dry-run only (no auto-apply)
atlas schema report --vault <vault> [--json]    # read-only; never scans/writes
atlas schema show --vault <vault> [--json]      # alias for report
```

## Explicit non-goals

- No automatic apply / rewrite of scanned artifacts in this package
- No dual-own of receipt_revocation / tombstones / retention cores
- No `apps/web`, PILOT invent, REL-001, or Atlas 2.0 production semantics
