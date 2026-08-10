# Atlas 2.0.0 — compatibility notes

Atlas 2.0.0 **consumes** the Atlas 1.0.0 compatibility anchor:

- `docs/releases/1.0.0/compatibility-anchor.json`
- Snapshot id: `atlas-1.0.0-compat`
- CLI: `atlas compat verify`

Conflict rule (unchanged): **1.0 wins**. Graph / KF2 / FED / PROV are not Layer B authority.

SYNC-001 / TWIN-001 production receipts embed `compat_snapshot_id` and refuse to run without a valid pin.
