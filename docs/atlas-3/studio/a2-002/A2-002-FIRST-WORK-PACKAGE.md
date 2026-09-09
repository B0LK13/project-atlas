# AS-STUDIO-A2-002 — Mission Journey (first work package)

```text
PACKAGE_ID                         = AS-STUDIO-A2-002
TITLE                              = Mission Journey RO vertical slice
BASE                               = certified A2 tip 2debb778 (explicit dependency)
BRANCH                             = feat/as-studio-a2-002-mission-journey
DEPENDS_ON_UNMERGED_A2             = YES (disclosed)
OVERLAP_AVOIDANCE                  = does not touch #782 intent target_repo binding;
                                     does not take over #781 visual shell
MUTATION_SURFACE                   = NONE (journey is read-only projection)
CLAIM_PATH                         = reuses existing preview/candidates only
FORMAL_IV                          = NOT_STARTED (new candidate)
MERGE_AUTHORIZATION                = NOT_GRANTED
```

## Selected user journey

> A user opens a mission, understands its status and relevant knowledge,
> identifies development context and the next permitted ownership action,
> previews its consequences, and sees how to continue into the existing
> governed claim path — without Studio self-authorizing.

```text
mission-control truth
  → knowledge plane (mission-relevant notes + provenance states)
  → development plane (repo / candidate / prerequisites)
  → claim candidates + optional preview (A2-001 reuse)
  → durable MISSION_JOURNEY packet (evidence, not authority)
```

## Why this slice (roadmap-aligned)

- Canonical phases: A1 = Mission Control, A2-001 = governed claim,
  A5 = full Knowledge Plane UX. Dependency law: *do not postpone existing
  knowledge features until A5 rebuild*.
- This package is **A2.x product glue**, not A3 runtime and not A5 chronicle.
- Vertical slice over many disconnected screens.

## Reuse (mandatory)

| Concern | Source |
|---|---|
| Mission status / attention / freshness | `atlas_studio.mission_control.build_mission_control` |
| Claim candidates / preview | `atlas_studio.action_intent` |
| Governance honesty | `atlas_studio.governance` (no new handlers) |
| Knowledge | existing vault indexes / OKF notes / `project_atlas` read lenses where available — **no parallel store** |
| Coordination truth | `atlas_dag` builders already used by A0/A1 |

## Non-goals

- Implementing CI_DISPATCH / IV_REQUEST / HANDOFF_DELIVER / STEAL_EXECUTE /
  MERGE / WORKTREE_OPEN.
- Changing `register_action` / certified A2 tip semantics.
- Taking over PR #782 `target_repo` intent binding.
- Tauri chrome (CLI + schema first; TUI text optional).
- Treating retrieved documents as authorization.

## Acceptance criteria

1. Schema `ATLAS_STUDIO_MISSION_JOURNEY_V1` validates.
2. CLI `atlas-studio mission-journey` (alias `journey`) emits the packet.
3. Knowledge section distinguishes: RETRIEVED / NONE_FOUND / UNAVAILABLE /
   STALE / INCOMPLETE.
4. Development section exposes repository, candidate identity fields from MC,
   and claim prerequisites without inventing eligibility.
5. Next action section surfaces claim candidates; optional `--preview-lane`
   attaches an A2 preview; never executes.
6. A1 remains free of governance imports; journey may *compose* MC + claim
   modules but UI/CLI still grants no authority.
7. Tests: success path, stale/unavailable knowledge, empty candidates,
   preview-attached path, honesty stamps.

## Interfaces affected

- New: `scripts/atlas_studio/mission_journey.py`
- New: `schemas/atlas_studio_mission_journey_v1.schema.json`
- Extend: `scripts/atlas_studio/cli.py`, doctor checks
- Docs: this directory + program README pointer
- Tests: `tests/unit/test_atlas_studio_a2_002_mission_journey.py`
