# AS-KF2 Wave 1 — Knowledge Fabric (ENTITY / REL / NS)

| Field | Value |
|---|---|
| Packages | **AS-KF2-NS-001**, **AS-KF2-ENTITY-001**, **AS-KF2-REL-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (Wave 1) |
| Class | **READY** (requires AS-2.0-COMPAT-001) |
| Authority | **derived only** — KF2 ≠ Layer B authority |

## Dependency

```text
AS-2.0-COMPAT-001 (1.0 anchor)
        │
        ▼
AS-KF2-NS-001 ──► AS-KF2-ENTITY-001 ──► AS-KF2-REL-001
```

Optional: entity may reference an AS-XPROJ-001 `global_entity_id` without
promoting XPROJ to authority.

## Surfaces

| Package | Schema | CLI |
|---|---|---|
| AS-KF2-NS-001 | `kf2-namespace` | `atlas kf2 namespace` |
| AS-KF2-ENTITY-001 | `kf2-entity` | `atlas kf2 entity` |
| AS-KF2-REL-001 | `kf2-relationship` | `atlas kf2 rel` |

Module: `project_atlas.kf2_fabric`  
Vault path: `generated/kf2/{namespaces,entities,relationships}/`

## Truth boundaries

- `KF2 NAMESPACE ≠ AUTHORITY`
- `KF2 ENTITY ≠ AUTHORITY`
- `KF2 RELATIONSHIP ≠ AUTHORITY`
- Graph≠authority remains in force

## Non-claims

- Not federation join (AS-2.0-FED-001)
- Not estate sync / authentic PILOT
- Not Atlas 2.0 RELEASE CERTIFIED
