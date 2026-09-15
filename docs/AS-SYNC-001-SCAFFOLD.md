# AS-SYNC-001-SCAFFOLD — Dry-run workspace registry

| Field | Value |
|---|---|
| Package | AS-SYNC-001-SCAFFOLD |
| CLI | `atlas sync registry dry-run --root … --vault … --vault-identity …` |
| Output | `generated/ops/workspace-registry-dry-run.json` only |

## Rules

- Explicit `--root` only — no whole-machine / home / FS-root scan
- Does not invent project UUIDs (quarantine instead)
- Does **not** write `00-system/sync/workspace-registry.json`
- `production_sync_certified: false` and `estate_pilot_passed: false` always

## Relation to AS-SYNC-001

Production SYNC-001 remains blocked on PILOT-003. This scaffold proves schema +
fail-closed dry-run paths on fixtures without claiming SYNC certified.
