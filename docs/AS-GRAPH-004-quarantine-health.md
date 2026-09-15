# AS-GRAPH-004 — Durable Quarantine / Health / Incremental

**Package:** AS-GRAPH-004  
**Stream:** Atlas Graph Layer  
**Status:** Implementation complete — IV-ready (governor certification required)  
**Depends on:** AS-GRAPH-003 soft quarantine candidates (consume; do not redefine)  
**Truth boundary:** `GRAPH QUARANTINE ≠ AUTOMATIC AUTHORITY`

## Purpose

Persist AS-GRAPH-003 soft `quarantine_candidate` records into a Core-owned
durable quarantine store, emit deterministic health counters, track
content-hash incremental state, and write immutable refresh receipts so
refreshes stay idempotent and fail-closed:

- durable records marked `status: quarantined` and `authority: derived`
- category remediation guidance (metadata only; no secret payloads)
- health rollup `healthy` / `degraded` / `unhealthy` / `unknown` from counters only
- incremental skip when input content hash is unchanged
- prepare → validate → promote with rollback on failure
- fail-closed on authority elevation, LWW promote into retained relationships,
  and claim-conflict synthesis

**Critical rule:** durable quarantine ≠ domain authority ≠ retained relationship.

## Persistence

Library entrypoints: `materialize_quarantine_store` /
`handoff_quarantine_store` (from `graph_relationships`) /
`write_quarantine_outputs`.

Optional vault emits are restricted to:

| Path | Role |
|---|---|
| `generated/graph/quarantine/<project_id>/*.json` | Durable quarantine records |
| `generated/graph/quarantine/<project_id>/receipt.json` | Immutable refresh receipt |
| `generated/graph/health/<project_id>/health.json` | Deterministic health counters |
| `generated/graph/incremental/<project_id>/state.json` | Incremental hash/state |

**Forbidden:** Control Plane `relationships/`, claims, temporal/authoritative
state, GRAPH-003 retained/relationship-quarantine prefixes, GRAPH-002
resolved/quarantine-candidates, knowledge-query caches.

## Incremental refresh

`input_content_hash` covers retained fingerprints, link-quality histogram, and
soft quarantine candidate payloads. Matching prior state sets
`incremental.refreshed=false`; `write_quarantine_outputs(..., skip_unchanged=True)`
returns planned paths without rewriting. Removed-artifact retention is
`deferred-explicit` (no autonomous GC).

No wall-clock timestamps appear in generated content (`generated.by` only).

## Invariants

- `GRAPH QUARANTINE ≠ AUTOMATIC AUTHORITY`
- `GRAPH HEALTH ≠ PROJECT AUTHORITY`
- Receipt `authority.graphify=derived` and `canonical_override_allowed=false`
- No LWW promote of quarantine into retained relationships
- No claim-conflict synthesis
- No CP `relationships/` writes
- Failed promote leaves prior vault state intact
- AS-GRAPH-002/003 certified semantics unchanged

## Out of scope

AS-GRAPH-005 (human MD projections), AS-XPROJ-002 (cross-project edges),
EXPLAIN Band B / QUERY-MULTI dual-own, CLI QUERY/EXPLAIN surfaces.
