# Atlas 2.0 — Dependency DAG

Status: **FROZEN against Atlas 1.0.0**. `ATLAS_2_0_IMPLEMENTATION_READY = YES`.

## Gate chain (normative for Track B)

```text
ATLAS_1_0_RELEASE_CERTIFIED = YES
        │
        ▼
docs/atlas-2.0 contracts + threat model + fixture plan COMPLETE
        │
        ▼
ATLAS_2_0_IMPLEMENTATION_READY = YES
        │
        ▼
2.0 production packages may open (FED / UX / PROV / SYNC / COMPAT)
```

## Certified 1.0 snapshot pin

- Software freeze commit: `f4079813025dd882e0e3608ab7ad5b3b17f95bd9`
- Software freeze tree: `feb0441a13e391812ae07a1a8eb27b0de1061469`
- Tag: `v1.0.0`
- Snapshot doc: `docs/releases/1.0.0/COMPATIBILITY-SNAPSHOT.md`

`DAG_DRAFT_COMPLETE = YES` · `DAG_FREEZE = YES`

## Package dependency sketch (§98)

```text
AS-2.0-COMPAT-001 ──consume──► 1.0 freeze snapshot (HEAD/TREE/tag)
AS-2.0-FED-001 ──depends──► AS-ID-001, AS-XPROJ-001, AT-013 path safety
AS-2.0-UX-001 ──depends──► WEB APPLICATION ACCEPTED, ADR-008/010, AS-J-005
AS-2.0-PROV-001 ──depends──► FR-004 deterministic-first, NFR-004 secrets, NFR-006
AS-2.0-SYNC-001 ──depends──► INT-013 (estate), CORE2-010 (fixture cert ≠ PILOT PASS),
                              INT-009/010 retention+tombstones, CORE2-009 recovery
```

## Soft-serialize notes

| Surface | Rule |
|---|---|
| 1.0 Core writers | 1.0 wins all dependency conflicts |
| `apps/web` | WEB 1.0 acceptance before AS-2.0-UX-001 |
| Estate SYNC | Authentic PILOT roots still required for production sync; fixture-only waiver does not open INT-013 production sync |

## Revalidation (2026-08-10)

DAG and §98 sketches revalidated against the certified 1.0 anchor above.
`2.0_PREP_COMPLETE_PENDING_1.0_ANCHOR` cleared.
