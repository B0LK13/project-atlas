# ADR-2.2-KF2-FABRIC-001 — Estate Knowledge Fabric PREP boundary

- Status: Accepted (PREP lane only)
- Package: `AS-2.2-KF2-FABRIC-PREP-001`
- Date context: Atlas 2.2 SAFE prep (tip `4cd646a`; `ATLAS_2_1_RELEASE_CERTIFIED = NO`)

## Context

AS-KF2-NS-001 / ENTITY-001 / REL-001 / AS-KF2-002 already ship on main as
derived Knowledge Fabric primitives (namespaces, entities, relationships,
count inventory export with `cross_promote=false`). The Atlas 2.2 roadmap
reserves `AS-2.2-KF2-FABRIC-001` for estate-scale inventory / projection
contracts ahead of `AS-2.2-INTEL-SLICE-001`. This package must land
docs/fixtures under `docs/atlas-2.2/kf2-fabric/**` without mutating runtime.

## Decision

1. Keep all new prep artifacts under `docs/atlas-2.2/kf2-fabric/**` (+ unique unit test).
2. Reference AS-KF2-* **conceptually**; do **not** mutate `project_atlas.kf2_fabric` / `kf2_inventory`.
3. Do **not** edit `docs/atlas-2.2/README.md` from this package (index owned elsewhere).
4. Freeze truth boundaries: KF2 ≠ AUTHORITY · NO CROSS PROMOTE · PROJECTION ≠ MUTATION · KF2 ≠ FED.
5. Record certification posture as:

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

Unlock remains `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` after `v2.1.0`.

## Consequences

- Fixture success grants no PILOT / RELEASE / gate credit.
- Post-unlock production work must compose over existing KF2 schemas rather
  than fork package_ids in docs stubs.
- Sibling workers may index this tree from `docs/atlas-2.2/README.md` without
  this package owning that index file.
