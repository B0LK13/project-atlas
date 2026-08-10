# AS-2.2-TIME-MACHINE-001 — Knowledge Time Machine + Diff (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-TIME-MACHINE-001** |
| Alias / directive form | `AS-2.2-TIME-MACHINE-001 PREP` |
| Class | **DOCUMENTATION_ONLY / CONTRACT_STUB / FIXTURE_SKETCH** |
| Status | **PREP** (SAFE pre-`v2.1.0`) |
| Gap | `GAP-NS-003` (feeds post-unlock `AS-2.2-TEMPORAL-001` + Diff UX) |
| Tip audited | `f45134f356a5862e59c9d4c23daa50b912b85598` |
| Tree | `02eeb7392a7cfcbf78a8c28a2034cf0b54ac509e` |
| Evidence | worktree `as-2.1-productionization-001` + `AS-COORD-CYCLE-2.1-011` item 6 |
| Sole-writer surface | `docs/atlas-2.2/time-machine/**` (+ this charter) |
| Production mutation | **NONE** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Problem

Operators need to answer: *what did the estate claim as-of T?* and *what
changed between T1 and T2?* — for claims, derived graph projections, and
decision/review dispositions — without inventing wall-clock “now”, without
mutating Layer B authority, and without conflating knowledge-time with
valid-time.

AS-2.0-TEMPORAL-001 already provides fail-closed **valid-time windows** and
**as-of selection** for a single subject/field. This PREP reserves the **Time
Machine** (as-of snapshot) and **Diff** (T1–T2 claim/graph/decision) contracts
for Atlas 2.2 intelligence — docs and fixtures only.

## User value

A governed as-of + diff design that can be fixture-tested and reviewed
**before** any 2.2 production wiring, without destabilizing the 2.1 tip.

## Scope (PREP)

| In | Out |
|---|---|
| Architecture + contract stubs | Live `bitemporal` / query API changes |
| As-of snapshot shape (claims/graph/decisions) | Wall-clock `now` / `today` as inputs |
| T1–T2 claim / graph / decision diff shapes | Silent winner selection on overlap |
| Fixture sketches under `time-machine/fixtures/` | CI gate credit / RELEASE / PILOT |
| Docs-only JSON Schema drafts | `src/project_atlas/schemas/` package-data bump |

## Owned surface

```text
docs/atlas-2.2/AS-2.2-TIME-MACHINE-001.md
docs/atlas-2.2/time-machine/**
```

## Excluded surface (do not dual-own)

- `project_atlas.bitemporal` runtime defaults / package_id
- `project_atlas.knowledge_compiler` authority / claim compile
- Claim Identity v2 inputs
- `api_server`, `authz`, Mission/Workspace/Ops web pages
- Authentic estate PILOT evidence

## Dependencies (consume-only)

| Depends on | Why |
|---|---|
| AS-CORE-005 / AS-2.0-TEMPORAL-001 | Valid-time windows + fail-closed as-of |
| AS-CORE-003 / conflict projections | Decision/review disposition substrate |
| AS-GRAPH-* derived projections | Graph slot ≠ authority |
| AS-2.0-COMPAT-001 / 1.0 wins | Conflict rule |

## Downstream (post-unlock)

- `AS-2.2-TEMPORAL-001` — validity windows / bitemporal UX receipts
- Time Machine read lens + Diff cockpit (future UX; UI≠canonical)
- Optional Ask Atlas 2 historical query planner

## Fail-closed (design intent)

1. Prefer **unresolved** over a wrong current / wrong diff winner.
2. No wall-clock `now` / `today` as valid-time or as-of input.
3. Overlapping validity covers → `unresolved_overlap` (no silent pick).
4. Graph / decision diffs are **derived**; never elevate to Layer B authority.
5. Fixture success ≠ PILOT PASS ≠ RELEASE CERTIFIED.

## Evidence requirements (PREP exit)

- [x] Architecture + contract docs landed
- [x] Docs-only schema stubs (as-of, T1–T2, claim/graph/decision diffs)
- [x] Fixture family reserved + sample payloads
- [ ] Post-`v2.1.0`: production package opens under unlock event

## Non-claims

- Not Time Machine LIVE_PRODUCTION
- Not a full bitemporal database
- Not authority resolution (AS-CORE-006)
- Not `ATLAS_2_1_RELEASE_CERTIFIED` / not `v2.2.0`
- Not dual-own of RET / CTX / KCI / DoD prep lanes
