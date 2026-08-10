# ADR-2.2-XPROJ-001 — Cross-project fabric PREP boundary

- Status: Accepted (PREP lane only)
- Package: `AS-2.2-XPROJ-CONTRACT-PREP-001`
- Date context: Atlas 2.2 SAFE prep (pre-`v2.1.0`)

## Context

AS-XPROJ-001..004 already ship on main as derived portfolio intelligence
primitives (global entities, edges, duplicate candidates, conflict indexes).
The Atlas 2.2 roadmap reserves `AS-2.2-XPROJ-001` for estate-scale fabric
composition ahead of `AS-2.2-ESTATE-OPS-001`. Harvest worker H03 must land
docs/fixtures under `docs/atlas-2.2/xproj/**` without mutating runtime.

## Decision

1. Keep all new prep artifacts under `docs/atlas-2.2/xproj/**` (+ unique unit test).
2. Reference AS-XPROJ-* **conceptually**; do **not** mutate `project_atlas.xproj_*`.
3. Do **not** edit `docs/atlas-2.2/README.md` from this package (index owned elsewhere).
4. Freeze truth boundaries: CROSS-PROJECT ≠ AUTHORITY · NAME ≠ IDENTITY · NO AUTOCOLLAPSE · INDEX ≠ RET-001.
5. Record certification posture as:

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

## Consequences

- Fixture success grants no PILOT / RELEASE / gate credit.
- Post-unlock production work must compose over existing XPROJ schemas rather
  than fork package_ids in docs stubs.
- Sibling workers may index this tree from `docs/atlas-2.2/README.md` without
  this package owning that index file.
