# ADR-2.2-ESTATE-OPS-001 — Estate operations lens (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-ESTATE-OPS-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b201c82` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

The 2.2 north-star roadmap places `AS-2.2-ESTATE-OPS-001` after cross-project
fabric (`AS-2.2-XPROJ-001`) to deliver estate-scale Mission Control /
Workspace / Ops Health lenses. Core already ships fail-closed ops health
snapshots (AS-OBS-001) and 2.1 web routes expose read-only lens stubs. Pre-unlock
work must not mutate that runtime while still landing reviewable estate-ops
contracts.

## Decision

1. Land cockpit architecture, JSON Schema stubs, and fixtures under
   `docs/atlas-2.2/estate-ops/**` only.
2. Treat `project_atlas.ops_health` / `ops_events` as **consume-only** until
   `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
3. Forbid unknown→healthy rollup invent, UI canonical writes, PILOT root invent,
   and ops runtime mutation in the estate-ops action vocabulary.
4. Do **not** mutate runtime `ops_health` / `ops_events` in this PREP PR.
5. Do **not** edit `docs/atlas-2.2/README.md` (index owned elsewhere).

## Consequences

- Positive: parallel-safe prep; clear fail-closed action wall; roadmap package
  has an owned doc surface distinct from XPROJ and web lens stubs.
- Negative: no live estate-ops cockpit until post-`v2.1.0` unlock; fixtures
  grant no gate credit.

## Non-decisions

- Exact Command Center panel layout vs separate routes
- Whether MCP `atlas.ops.health.read` embeds receipts vs deep-links
- Any change to Core ops health defaults or web lens stub content
