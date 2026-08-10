# Knowledge Fabric estate — fixture plan (PREP)

Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/kf2-fabric/fixtures/`
are synthetic sketches. **Gate credit: NO.** Runner: absent until post-unlock.

## Family

| Family | Path | Package |
|---|---|---|
| kf2-fabric | `docs/atlas-2.2/kf2-fabric/fixtures/` | AS-2.2-KF2-FABRIC-PREP-001 |

## Scenarios

| ID | File | Intent |
|---|---|---|
| FX-2.2-KF2-001 | `fabric-inventory.fixture.json` | Full estate inventory citing AS-KF2-* buckets |
| FX-2.2-KF2-002 | `namespace.sample.json` | Explicit namespace citation (conceptual) |
| FX-2.2-KF2-003 | `entity.sample.json` | Explicit entity citation; optional XPROJ cite ≠ authority |
| FX-2.2-KF2-004 | `relationship.sample.json` | Explicit relationship citation; Graph≠authority |
| FX-2.2-KF2-005 | `inventory-export.sample.json` | AS-KF2-002 count export citation; cross_promote=false |
| FX-2.2-KF2-006 | `negative-cross-promote.expect.json` | Cross-promote → reject expect |
| FX-2.2-KF2-007 | `negative-authority-elevate.expect.json` | Authority elevate → reject expect |
| FX-2.2-KF2-008 | `negative-projection-write.expect.json` | Projection write → reject expect |

## Rules

- `evidence_class = fixture-only`
- `pilot_roots = 0`
- `cross_promote = false`
- `atlas_2_1_release_certified = false`
- Synthetic relative paths only; no host-specific estate roots
- No secrets / credentials / personal data in payloads
- Never stamp WEB / RELEASE / 2.1 READY / PILOT PASS
- Never dual-own AS-KF2 emit paths from fixtures

## Inventory state

| Scenario | State | Gate credit |
|---|---|---|
| FX-2.2-KF2-001..008 | payload-present (docs sketch) | **NO** |

Promotion to `fixtures/atlas-2.2/` + harness requires
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
