# AS-SYNC-002-SCAFFOLD — Deterministic dry-run sync plan

| Field | Value |
|---|---|
| Package | AS-SYNC-002-SCAFFOLD |
| Library | `project_atlas.sync_plan.build_dry_run_sync_plan` |
| Input | Explicit workspace-registry dry-run document (fixture or `build_dry_run_registry`) |
| Output | `generated/ops/sync-plan-dry-run.json` (optional write helper) |
| Schema | `sync-plan-dry-run` → `schemas/sync-plan-dry-run.schema.json` |

## Rules

- Explicit registry document only — no whole-machine / home / FS-root scan
- Does **not** invent project UUIDs or PILOT roots
- Does **not** write `00-system/sync/` production registry or plan paths
- `production_sync_certified: false` and `estate_pilot_passed: false` always
- Ordered `project_order` + per-entry dispositions: `eligible` / `quarantined` / `disabled`
- Checkpoint / retry-resume fields are stubs (`null` / empty) — scaffold ≠ SYNC-002 certified

## CLI

No new CLI in this scaffold. `atlas sync …` remains owned by AS-SYNC-001
(`workspace_registry`). A thin `atlas sync plan dry-run` may be added later
once registry ownership is stable across lanes.

## Relation to AS-SYNC-002

Production SYNC-002 (estate sync with retry/resume) remains out of scope.
This scaffold proves deterministic plan emission + schema on fixtures without
claiming SYNC-002 certified or estate PILOT PASS.
