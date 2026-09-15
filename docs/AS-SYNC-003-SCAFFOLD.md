# AS-SYNC-003-SCAFFOLD — Dry-run queue/retry/resume scaffold

AS-SYNC-003-SCAFFOLD is a library-only deterministic projection from an explicit, schema-valid AS-SYNC-002 dry-run sync plan. It does not scan the home directory, a filesystem root, an empty root, or any estate path.

The library emits ordered queue entries with inert retry-policy, resume-cursor, and estate-receipt stubs. Output may be persisted only as `generated/ops/sync-queue-dry-run.json`; writes under `00-system/sync/` fail closed. There is intentionally no CLI integration in this lane.

## Explicit non-claims

- This scaffold is **not** production SYNC certification.
- This scaffold is **not** an estate PILOT PASS.
- It does not execute synchronization, retries, resume, or receipt issuance.
- It does not discover or invent estate roots, projects, or project UUIDs.
- `production_sync_certified` and `estate_pilot_passed` are schema-locked to `false`.

The `sync-queue-dry-run` schema is the contract for this operational, non-authoritative artifact.
