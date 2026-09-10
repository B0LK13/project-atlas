# AS-STUDIO-A1-001 — evidence (Mission Control)

```text
AS_STUDIO_A1_001 = TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED
IMPLEMENTED != MERGED
CI_PASS != FORMAL_IV
MERGE_AUTHORIZATION = NOT_GRANTED
STUDIO_MUTATION_AUTHORITY = NONE
MISSION_CONTROL_HUMAN_COHERENCE = PROVEN
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
| HEAD (tip) | `3d76fa0e…` (+ A1 semantic-boundary closure edits) |
| PR | https://github.com/B0LK13/project-atlas/pull/770 |
| Local tests | **40 passed** = 15 A0 + 15 A1 contract + 10 semantic attacks; ruff PASS |
| Schema | `schemas/atlas_studio_mission_control_v1.schema.json` |
| Module | `scripts/atlas_studio/mission_control.py` |
| CLI | `scripts/atlas-studio.py mission-control` / `mc` |
| Tests | `tests/unit/test_atlas_studio_a1_mission_control.py`, `tests/unit/test_atlas_studio_a1_semantic_boundaries.py` |
| Closure | `docs/atlas-3/studio/a1/A1-CLOSURE.md` |
| Freshness | `docs/atlas-3/studio/a1/FRESHNESS.md` |

## Validation (lane)

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a0.py \
  tests/unit/test_atlas_studio_a1_mission_control.py \
  tests/unit/test_atlas_studio_a1_semantic_boundaries.py -q --tb=short --no-cov
.venv/bin/python -m ruff check scripts/atlas_studio \
  tests/unit/test_atlas_studio_a1_semantic_boundaries.py
.venv/bin/python scripts/atlas-studio.py doctor --json
.venv/bin/python scripts/atlas-studio.py mc --json
```

### Results (closure run)

| Gate | Result |
|---|---|
| pytest A0+A1+semantic | **40 passed** |
| ruff `scripts/atlas_studio` + semantic suite | **PASS** |
| Live `mc --json` | `mission_status=HUMAN_ATTENTION_REQUIRED`, `freshness=LIVE`, `attention_count=8`, `honesty.attention_ne_authorization=true`, fingerprint prefix `16995f10141dfd21` |

## Semantic attack suite (`test_atlas_studio_a1_semantic_boundaries.py`)

| # | Attack | Outcome |
|---|---|---|
| 1 | Highest-ranked attention ≠ authorized | PASS — `attention_ne_authorization`; forged `authorized=true` fails validation |
| 2 | STALE cannot validate as HEALTHY | PASS |
| 3 | UNKNOWN seal/evidence cannot validate as HEALTHY | PASS |
| 4 | Foreign agent matrix cannot fabricate frontier | PASS — `AGENT_MATRIX_MISMATCH` → DEGRADED; rankings suppressed |
| 5 | Nested dishonest control_view honesty | PASS — A0 fail-closed path |
| 6 | Empty/malformed views fail validation | PASS |
| 7 | No mutation symbols in `atlas_studio` | PASS |
| 8 | Rankings == F12 `typed_rankings` byte-for-byte | PASS — no Studio re-rank |
| 9 | Distinct injections → distinct fingerprints | PASS — no sticky authorize cache |
| 10 | Attention ordering deterministic | PASS |

## Design laws exercised

| Law | Evidence |
|---|---|
| STUDIO_UI != AUTHORITY | honesty consts + schema `const: true` |
| MISSION_CONTROL = PROJECTION | embeds A0 snapshot; F15 panels; F12 matrix projection only |
| ATTENTION != AUTHORIZATION | attention items require `attention_ne_authorization`; auth flags rejected |
| STALE != CURRENT | freshness.state STALE ⇒ mission_status STALE; HEALTHY validation refused |
| UNKNOWN != HEALTHY | seal/evidence UNKNOWN cannot validate as HEALTHY |
| NO_MUTATION_API_IN_A1 | AST/API denial tests (contract + semantic) |
| REUSE_BUILDERS | `build_frontier_matrix` / control_view / telemetry / residuals |
| A0 nested honesty fail-closed | dishonest CV honesty raises; cannot be OK/HEALTHY |
| Agent/matrix binding | foreign matrix DEGRADED + suppressed rankings/attention |

## F12 → action classes

When `frontier_matrix` is injected or built live (agent present **and** matrix
agent matches), Mission Control `views.frontier.action_classes.by_action_class`
and `views.frontier.rankings.typed_rankings` are copied from F12 without
re-ranking. Agent mismatch → DEGRADED / suppressed. Matrix absent → UNKNOWN
(not fake empty OK).

## Non-claims

- Not merged to main; not formal IV; no Tauri; no A2 mutations; no atlasd binary.
- `CI_PASS != FORMAL_IV`; verifiers unbound ⇒ `EXTERNAL_IV_GATED` not CERTIFIED.
