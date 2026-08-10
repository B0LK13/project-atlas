# Atlas 2.0 — Dependency DAG

Status: **FROZEN against Atlas 1.0.0**. `ATLAS_2_0_IMPLEMENTATION_READY = YES`.
`ATLAS_2_0_PRODUCTION_IMPLEMENTATION = AUTHORIZED`.

## Gate chain

```text
ATLAS_1_0_RELEASE_CERTIFIED = YES
        │
        ▼
ATLAS_1_0_COMPATIBILITY_ANCHOR_CONFIRMED
        │
        ▼
ATLAS_2_0_IMPLEMENTATION_READY = YES · GATE_10 UNLOCKED
        │
        ▼
Wave 1: AS-2.0-COMPAT-001 → AS-KF2-NS/ENTITY/REL
        │
        ▼
Later waves: FED / temporal / twin / KCI / context / agent / UX2 / platform / estate
```

## Certified 1.0 snapshot pin

- Software freeze commit: `f4079813025dd882e0e3608ab7ad5b3b17f95bd9`
- Software freeze tree: `feb0441a13e391812ae07a1a8eb27b0de1061469`
- Tag: `v1.0.0` @ `bb0957c47b5e2976b5cf358342cf89dffe6e6a55`
- Machine record: `docs/releases/1.0.0/compatibility-anchor.json`

`DAG_DRAFT_COMPLETE = YES` · `DAG_FREEZE = YES`

## Package dependency sketch

```text
AS-2.0-COMPAT-001 ──consume──► 1.0 freeze snapshot (HEAD/TREE/tag)
AS-KF2-NS-001 ──depends──► AS-2.0-COMPAT-001
AS-KF2-ENTITY-001 ──depends──► AS-KF2-NS-001 (± optional XPROJ global id)
AS-KF2-REL-001 ──depends──► AS-KF2-ENTITY-001
AS-2.0-FED-001 ──depends──► AS-ID-001, AS-XPROJ-001, AT-013, COMPAT
AS-2.0-UX-001 ──depends──► WEB APPLICATION ACCEPTED, ADR-008/010, AS-J-005
AS-2.0-PROV-001 ──depends──► FR-004, NFR-004, NFR-006, COMPAT
AS-2.0-SYNC-001 ──blocked──► authentic estate PILOT (fixture waiver ≠ 2.0 final)
AS-2.0-TWIN-001 ──blocked──► authentic estate PILOT
```

## Soft-serialize notes

| Surface | Rule |
|---|---|
| 1.0 Core writers | 1.0 wins all dependency conflicts |
| KF2 fabric | Derived only; never Layer B authority |
| Estate SYNC / Twin | Authentic PILOT required for 2.0 final certification |
