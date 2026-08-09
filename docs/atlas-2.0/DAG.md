# Atlas 2.0 — Dependency DAG (prep)

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

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

While `ATLAS_1_0_RELEASE_CERTIFIED = NO`, Track B may only deepen docs/ADRs/contracts/fixtures.

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
| Estate SYNC | Blocked until authentic PILOT roots or explicit fixture-only auth |

## Idle deepen (2026-08-09)

Expanded gate chain + package dependency sketch. Still **PREP ONLY**.
