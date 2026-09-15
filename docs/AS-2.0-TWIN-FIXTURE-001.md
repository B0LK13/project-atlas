# AS-2.0-TWIN-FIXTURE-001 — Disposable twin projection fixtures

| Field | Value |
|---|---|
| Package | **AS-2.0-TWIN-FIXTURE-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **FIXTURE / PREP-SAFE** |
| Class | Fixture lane only — **not** AS-2.0-TWIN-001 production |

## Purpose

Disposable Digital Twin projection fixtures for harness rehearsal under
`docs/atlas-2.0/fixtures/twin-projection/` and `tests/fixtures/atlas-2.0/twin-projection/`.

## Surfaces

| Surface | Path |
|---|---|
| Schema | `twin-projection-fixture` |
| Module | `project_atlas.twin_fixtures` |
| CLI | `atlas twin-fixture build` |
| Vault output | `generated/ops/twin-fixtures/<projection_id>.json` |

## Invariants

- `estate_pilot_passed = false` always
- `twin_production_ready = false` always
- `twin_001_status = BLOCKED` always
- `authentic_pilot_roots = 0` demotes any requested `healthy` row to `unknown`
- Bound to `atlas-1.0.0-compat`
- Twin ≠ authority; fixture twin ≠ PILOT PASS

## Explicit non-claims

- **NOT** `ESTATE PILOT PASSED`
- **NOT** `AS-2.0-TWIN-001` production READY
- Authentic `AS-2.0-TWIN-001` remains **BLOCKED** without authentic PILOT
