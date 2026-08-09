# AS-XPROJ-001 — Global / shared entity identity registry

Package guide for the first cross-project primitive: **explicit global entity
registration** with additive join keys. This is governed portfolio intelligence
(Layer C / derived). It is **not** claim truth, temporal current, or domain
authority.

## Truth boundary

```text
CROSS-PROJECT IDENTITY ≠ AUTOMATIC AUTHORITY
NAME / STRING ≠ IDENTITY
SAME DISPLAY NAME ≠ SAME CLASS INSTANCE
```

Registry records always carry `authority.level = derived`.

## Explicit registration only

- Global entities exist only via schema-valid registration records.
- Join keys map `(project_id, project_local_entity_id) → global_entity_id`
  **only** through registration — never display-name equality, slugify, fuzzy,
  embedding, or LLM clustering.
- Identical technology strings across projects remain **distinct** until both
  locals are explicitly joined to the same `global_entity_id`.

## Ontology (MVP classes)

`technology`, `service`, `library`, `infrastructure`, `environment`,
`external-api`, `organization`, plus `extension` / quarantine for unknowns.

Same display name as `technology` vs `service` → **different** global IDs.
Physical / inventory resources (host, ARN, disk, NIC) must **not** be
auto-promoted to `technology` / `service`.

## Persistence (frozen)

| Path | Role |
|---|---|
| `state/global-entities/*.json` | Global entity records |
| `state/global-entities/joins/*.json` | Join keys |
| `state/global-entities/quarantine-candidates/*.json` | Ambiguous / forbidden attempts |

Never write claims, `state/current-state/`, `state/authoritative-state/`,
knowledge-query caches, Control Plane `relationships/`, or Graph Layer paths.

## CLI

```bash
atlas register-global-entity --registrations regs.json
atlas register-global-entity --registrations regs.json --vault <vault> --write
```

Registrations file shape:

```json
{
  "registrations": [
    {
      "kind": "entity",
      "global_entity_id": "ge-tech-postgres-v1",
      "entity_class": "technology",
      "display_name": "Postgres"
    },
    {
      "kind": "join",
      "project_id": "proj-a",
      "project_local_entity_id": "proj-a:unknown:postgres",
      "global_entity_id": "ge-tech-postgres-v1",
      "evidence_refs": [
        { "relative_path": "sources/arch.md", "sha256": "<64-hex>" }
      ]
    }
  ]
}
```

## Privacy / project boundary

Registering a join does **not** grant cross-project read of private source
trees. Evidence refs remain project-scoped even when a global ID exists
(`AS-XPROJ-INV-EVIDENCE-001`). Secret-shaped fields must not appear in
registry records.

## Out of scope

- Cross-project edges → **AS-XPROJ-002**
- Duplicate-project detection → **AS-XPROJ-003**
- Conflict indexes / projections → **AS-XPROJ-004**
- Graph-002/003 semantics (consume-only)
- MODEL-001B / knowledge_compiler surfaces

## Library API

`project_atlas.xproj_registry`: `register_global_entity`, `register_join`,
`apply_registrations`, `write_registry_outputs`, `inspect_registry`.
