# AS-STUDIO-A1-001 — evidence (Mission Control)

```text
AS_STUDIO_A1_001 = IMPLEMENTED_IN_LANE
IMPLEMENTED != MERGED
CI_PASS != FORMAL_IV
MERGE_AUTHORIZATION = NOT_GRANTED
STUDIO_UI != AUTHORITY
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
NO_MUTATION_API_IN_A1
O1 = APPROVED (in-process atlas_dag RO runtime)
O6 = APPROVED (seal/evidence may be UNKNOWN; never promote to healthy)
```

## Exact objects

| Field | Value |
|---|---|
| Package | `AS-STUDIO-A1-001` |
| Branch | `feat/as-studio-a1-001` |
| Base | A0 tip `efb92255…` / PR #763 lineage |
| HEAD (tip) |  |
| PR | https://github.com/B0LK13/project-atlas/pull/770 |
| Local tests | 15 A0 + 13 A1 = 28 passed; ruff PASS; doctor PASS |
| Schema | `schemas/atlas_studio_mission_control_v1.schema.json` |
| Module | `scripts/atlas_studio/mission_control.py` |
| CLI | `scripts/atlas-studio.py mission-control` / `mc` |
| Tests | `tests/unit/test_atlas_studio_a1_mission_control.py` |
| Freshness | `docs/atlas-3/studio/a1/FRESHNESS.md` |

## Validation (lane)

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a0.py \
  tests/unit/test_atlas_studio_a1_mission_control.py -q --tb=short --no-cov
.venv/bin/python -m ruff check scripts/atlas_studio \
  tests/unit/test_atlas_studio_a1_mission_control.py
.venv/bin/python scripts/atlas-studio.py doctor --json
.venv/bin/python scripts/atlas-studio.py mc --json
```

## Design laws exercised

| Law | Evidence |
|---|---|
| STUDIO_UI != AUTHORITY | honesty consts + schema `const: true` |
| MISSION_CONTROL = PROJECTION | embeds A0 snapshot; F15 panels; F12 matrix projection only |
| ATTENTION != AUTHORIZATION | attention items require `attention_ne_authorization` |
| STALE != CURRENT | freshness.state STALE ⇒ mission_status STALE |
| UNKNOWN != HEALTHY | seal/evidence UNKNOWN cannot validate as HEALTHY |
| NO_MUTATION_API_IN_A1 | AST/API denial tests |
| REUSE_BUILDERS | `build_frontier_matrix` / control_view / telemetry / residuals |
| A0 nested honesty fail-closed | dishonest CV honesty raises; cannot be OK/HEALTHY |

## F12 → action classes

When `frontier_matrix` is injected or built live (agent present), Mission Control
`views.frontier.action_classes.by_action_class` and `views.frontier.rankings.typed_rankings`
are copied from F12 (`ATLAS_MULTIDIMENSIONAL_FRONTIER_V1`) without re-ranking.
HUMAN_GATE / OWNER_DECISION action ids feed `views.human_gates` and attention.
When matrix is absent: action_classes/rankings status = UNKNOWN (not fake empty OK).

## Non-claims

- Not merged to main; not formal IV; no Tauri; no A2 mutations; no atlasd binary.
