# AS-SYNC-004-SCAFFOLD - Estate-receipt and trigger stubs

AS-SYNC-004-SCAFFOLD is a library-only deterministic projection from an explicit, schema-valid AS-SYNC-003 dry-run queue document. It never discovers or scans a home directory, filesystem root, empty root, estate root, or project path.

The projection emits one inert estate-receipt stub and two disabled trigger placeholders (`on_change` and `on_schedule`) for each ordered queue entry. It does not issue receipts, register triggers, evaluate schedules, watch files, or synchronize content. Output may be persisted only as `generated/ops/sync-receipts-dry-run.json`; writes under `00-system/sync/` and vault-escaping symlink paths fail closed. There is intentionally no CLI integration in this lane.

## Explicit non-claims

- This scaffold **≠ production SYNC certification**.
- This scaffold **≠ estate PILOT PASS**.
- `production_sync_certified` and `estate_pilot_passed` are schema-locked to `false`.
- Estate receipts remain `not_issued` with null IDs and evidence hashes.
- Trigger placeholders remain disabled and unregistered with null expressions.

The `sync-receipts-dry-run` schema is the contract for this operational, non-authoritative artifact.
