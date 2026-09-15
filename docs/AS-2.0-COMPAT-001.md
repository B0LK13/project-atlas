# AS-2.0-COMPAT-001 — Compatibility snapshot consumer

| Field | Value |
|---|---|
| Package | **AS-2.0-COMPAT-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (Wave 1) |
| Class | **READY** |

## Purpose

Machine-readable Atlas 1.0 compatibility anchor and fail-closed consumer so
every Atlas 2.0 package binds the certified freeze pin.

## Anchor

| Field | Value |
|---|---|
| File | `docs/releases/1.0.0/compatibility-anchor.json` |
| Snapshot ID | `atlas-1.0.0-compat` |
| Freeze HEAD | `f4079813025dd882e0e3608ab7ad5b3b17f95bd9` |
| Freeze TREE | `feb0441a13e391812ae07a1a8eb27b0de1061469` |
| Tag | `v1.0.0` @ `bb0957c…` |

## Surfaces

- Schema: `compatibility-anchor`
- Module: `project_atlas.compat_anchor`
- CLI: `atlas compat verify`

## Invariants

- 1.0 wins dependency conflicts
- Drift against expected freeze HEAD/TREE/tag fails closed
- Does not claim authentic estate PILOT PASS
- Does not stamp Atlas 2.0 RELEASE CERTIFIED
