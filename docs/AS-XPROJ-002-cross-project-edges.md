# AS-XPROJ-002 — Cross-project relationship rules

Package guide for **explicit cross-project edges** between registered global
entities (AS-XPROJ-001). This is governed portfolio intelligence (Layer C /
derived). It is **not** claim truth, temporal current, domain authority, or a
substitute for project-local AS-GRAPH-003 relationships.

## Truth boundary

```text
CROSS-PROJECT EDGE ≠ AUTOMATIC AUTHORITY
NAME / STRING ≠ ENDPOINT IDENTITY
GRAPH-003 INTRA-PROJECT ≠ XPROJ CROSS-PROJECT
conflicts-with ≠ Core claim-conflict synthesis
```

Edge records always carry `authority.level = derived`.

## Explicit registration only

- Edges exist only via schema-valid registration records with explicit
  `edge_id`, `relationship_type`, and **both** `source_global_entity_id` /
  `target_global_entity_id`.
- Endpoints must already be registered in the XPROJ-001 global entity registry
  (AS-XPROJ-INV-EXPLICIT-001).
- Display-name equality, slugify, fuzzy, embedding, or LLM clustering must
  **never** mint endpoints or edges (AS-XPROJ-INV-NO-FUZZY-001).

## Cross-project span rule

An edge is retained only when the union of join-covered `project_id`s for its
two endpoints spans **≥ 2** distinct projects. Single-project (intra-project)
edges belong to **AS-GRAPH-003** and are quarantined here as `not-cross-project`
(AS-XPROJ-INV-EDGE-001).

## Relationship vocabulary

Mirrors GRAPH-003 MVP types (consume-only; this package does not mutate graph
modules):

`part-of`, `depends-on`, `documents`, `validates`, `supersedes`,
`derived-from`, `conflicts-with`, plus `extension` (requires `extension_type`).

`conflicts-with` is stored as a derived edge only — it must **never** invent
Core claim conflicts or elevate authority.

## Persistence (frozen)

| Path | Role |
|---|---|
| `state/global-entities/edges/*.json` | Retained global edge records |
| `state/global-entities/edge-quarantine/*.json` | Fail-closed quarantine candidates |

Never write claims, `state/current-state/`, `state/authoritative-state/`,
knowledge-query caches, Control Plane `relationships/`, Graph Layer paths, or
XPROJ-001 entity/join files from this package.

## CLI

```bash
atlas register-global-edge --edges edges.json --vault <vault>
atlas register-global-edge --edges edges.json --vault <vault> --write
```

`--vault` is required (endpoints are resolved from XPROJ-001 registry state).

Edges file shape:

```json
{
  "edges": [
    {
      "kind": "edge",
      "edge_id": "xe-dep-billing-postgres-v1",
      "relationship_type": "depends-on",
      "source_global_entity_id": "ge-svc-billing",
      "target_global_entity_id": "ge-tech-postgres-v1",
      "link_quality": "supported",
      "evidence_refs": [
        { "relative_path": "sources/arch.md", "sha256": "<64-hex>" }
      ]
    }
  ]
}
```

## Fail-closed quarantine categories

| Category | Meaning |
|---|---|
| `missing-endpoint-registration` | One or both globals not registered |
| `name-only-edge-forbidden` | Display-name / mint-from-names attempt |
| `fuzzy-edge-forbidden` | Fuzzy / similarity join attempt |
| `not-cross-project` | Join coverage spans &lt; 2 projects |
| `self-loop-forbidden` | Source == target |
| `incompatible-duplicate-edge` | Same endpoints+type, different fingerprint (no LWW) |
| `unknown-relationship-type` | Outside MVP vocabulary |
| `endpoint-guess-forbidden` | Missing / invalid global endpoint ids |
| `evidence-refs-required` | Missing or malformed evidence |
| `secret-finding` | Secret-shaped notes/extension redacted + quarantine |
| `edge-id-invalid` | Missing / malformed edge id |

Quarantine never includes `winning_choice`.

## Privacy / project boundary

Registering a cross-project edge does **not** grant cross-project read of
private source trees. Evidence refs remain project-scoped paths even when a
global edge exists.

## Out of scope

- Duplicate-project detection → **AS-XPROJ-003**
- Conflict indexes / projections → **AS-XPROJ-004**
- GRAPH-002/003/004 module mutation (consume-only for types / patterns)
- `knowledge_compiler`, QUERY, EXPLAIN surfaces
- CP `relationships/` as truth

## Library API

`project_atlas.xproj_edges`: `register_global_edge`, `apply_edge_registrations`,
`write_edge_outputs`, `inspect_edge_registry`, `load_edge_registry_state`,
`compute_edge_fingerprint`.
