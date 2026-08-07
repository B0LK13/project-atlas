# AS-CORE-006 — Domain-Specific Authority

**Status:** Implementation package (Level 2 ingredient; not Level 3)  
**Trust root:** versioned code-level authority registry  
**MVP rule:** `R-TITLE-001` only

## Pipeline

```text
immutable claims
  → AS-CORE-005 temporal disposition (current / historical / unresolved / authority-pending)
  → AS-CORE-006 authority evaluation
  → derived authoritative state
```

Temporal current and authoritative current are **distinct**. A temporally
current claim is not automatically authoritative. An authoritative role does
not resurrect a temporally historical claim.

## Trust root

Authority is not established because a document says “canonical”,
“authoritative”, “source of truth”, “final”, or “official”.

Trust chain:

1. Owner authorization of a Core package change
2. Certified repository commit containing the registry
3. Explicit `authority_registry_version`
4. Deterministic evaluation against that registry

Self-asserting documents are evidence inputs only.

## Registry

Module: `project_atlas.authority_registry`

- Version: `AUTHORITY_REGISTRY_VERSION = 1`
- Trust root id: `code-level-authority-registry/v1 (owner-certified Core package AS-CORE-006)`
- Rules are inspectable, deterministic, and free of recency heuristics

MVP encodes **only** rules proven by the entry gate. No global source hierarchy.

## Domain: `work_package.durable_title`

Applies when:

- subject starts with `wp:`
- field is `title`

Does **not** govern package status, certification, roadmap rows, or merge state.

## Rule R-TITLE-001

For the durable work-package title domain, `package_genesis_receipt` is
authoritative. Remediation episode titles and later operational titles do not
replace the durable package title merely because they were observed later.

Acceptance fixture: `wp:AS-ID-001 / title`

- Authoritative value: `Durable Source Lineage Identity`
- Role: `package_genesis_receipt`
- Competing remediation titles remain preserved and subordinate

## Fail-closed policy

| Condition | Disposition |
|---|---|
| No registry rule | no authoritative selection (evaluator skips domain) |
| Role cannot be established | `authority-pending` |
| No genesis-role claim among temporally eligible | `authority-pending` |
| Multiple genesis-role claims with conflicting values | `authority-conflict` |
| Historical claim with authoritative role | not resurrected |

Never fall back to observation recency, ordinal, path order, or lexical order
to break conflicting equal-authority values.

## Derived output

`state/authoritative-state/{project}.json` holds `authoritative_states`.

AS-CORE-005 `state/current-state/` remains unchanged in meaning.

## Artifact roles

Resolved from structured YAML + governed path shapes
(`project_atlas.authority_roles`):

- `package_genesis_receipt` — `docs/evidence/{PACKAGE}-receipt.yaml` with
  matching `package`/`title` and no remediation markers
- `remediation_episode_receipt` — remediation / wiring / review episode markers
- `unknown` — insufficient structured evidence (fail closed)

## Limitations

- MVP contains a single proven domain rule
- Does not claim universal authority resolution
- Does not implement a Knowledge Query Contract
- Does not modify Claim Identity V2 or AS-CORE-005 temporal semantics
- `docs/plan.md` roadmap multi-row collapse remains an extraction issue, not authority

## Future boundary

A later Knowledge Query Contract may consume `authoritative_states` and
explanations. No query API is provided here.
