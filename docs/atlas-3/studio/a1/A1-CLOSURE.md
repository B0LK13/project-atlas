# AS-STUDIO-A1-001 — technical closure (Mission Control)

```text
AS_STUDIO_A1_001 = TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED
MISSION_CONTROL_HUMAN_COHERENCE = PROVEN
STUDIO_MUTATION_AUTHORITY = NONE
MERGE_AUTHORIZATION = NOT_GRANTED
CI_PASS != FORMAL_IV
IMPLEMENTED != MERGED
VERIFIERS_UNBOUND → EXTERNAL_IV_GATED (not CERTIFIED)
STUDIO_UI != AUTHORITY
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
NO_MUTATION_API_IN_A1
```

Honest stamp: local/exact-object CI green is **not** formal IV. Verifier pool
remains unbound on this estate → status is **EXTERNAL_IV_GATED**, not
`CERTIFIED` / `FORMAL_IV_PASS`.

## Exact object

| Field | Value |
|---|---|
| Package | `AS-STUDIO-A1-001` |
| Branch | `feat/as-studio-a1-001` |
| HEAD (closure tip) |  |
| PR | https://github.com/B0LK13/project-atlas/pull/770 |
| Schema | `schemas/atlas_studio_mission_control_v1.schema.json` |
| Module | `scripts/atlas_studio/mission_control.py` |
| CLI | `atlas-studio mission-control` / `mc` |
| Contract tests | `tests/unit/test_atlas_studio_a1_mission_control.py` (15) |
| Adversarial tests | `tests/unit/test_atlas_studio_a1_semantic_boundaries.py` (10) |
| A0 baseline | `tests/unit/test_atlas_studio_a0.py` (15) |
| Combined gate | **40 passed** (15+15+10); ruff PASS on `scripts/atlas_studio` + semantic suite |
| Freshness law | `docs/atlas-3/studio/a1/FRESHNESS.md` |
| Evidence | `docs/atlas-3/studio/a1/A1-EVIDENCE.md` |

## Mission Control human coherence = PROVEN

A human can answer “what matters next / what is blocked / what is unknown”
from one Mission Control surface without reconstructing F12/F15 by hand.

| Evidence | Result |
|---|---|
| Attention ranking carries `attention_ne_authorization` only (no auth flags) | `test_highest_ranked_attention_item_is_not_authorized` |
| STALE cannot validate as HEALTHY | `test_stale_mission_control_cannot_validate_as_healthy` |
| UNKNOWN seal/evidence cannot validate as HEALTHY | `test_unknown_seal_evidence_cannot_validate_as_healthy` |
| Foreign agent matrix cannot fabricate frontier | `test_foreign_agent_matrix_cannot_fabricate_frontier` |
| Nested dishonest CV honesty fail-closed (A0 path) | `test_nested_dishonest_control_view_cannot_yield_ok_healthy` |
| Empty/malformed views fail validation | `test_empty_or_malformed_views_fail_validation` |
| No mutation symbols in `atlas_studio` | `test_no_mutation_symbols_in_atlas_studio_package` |
| Rankings = F12 `typed_rankings` byte-for-byte | `test_ranking_projection_equals_f12_typed_rankings_byte_for_byte` |
| Distinct injections → distinct fingerprints | `test_cached_old_fingerprint_two_builds_differ` |
| Attention order deterministic | `test_attention_ordering_deterministic_for_identical_inputs` |
| Live `atlas-studio mc --json` (lane) | `mission_status=HUMAN_ATTENTION_REQUIRED`, `freshness=LIVE`, `attention_count=8`, `honesty.attention_ne_authorization=true` |

## Fail-closed agent/matrix binding (narrowed weakness)

**Chosen behavior:** when Mission Control is built with `agent_id=A` and an
injected F12 matrix declares `agent=B≠A`, frontier status becomes **DEGRADED**
with note `AGENT_MATRIX_MISMATCH`; `typed_rankings` / `by_action_class` are
suppressed (`None`); attention does not emit foreign `matrix-gate:*` /
`blocked-hv:*` items; `mission_status` cannot validate as `HEALTHY` under
mismatch notes.

This closes the prior hole where a foreign matrix could still paint another
agent’s frontier into a drill-down for `A`.

## Remaining owner decisions

| ID | Decision | Default if unbound |
|---|---|---|
| O1 | RO runtime | **APPROVED** — in-process `atlas_dag` |
| O6 | Seal/evidence UNKNOWN | **APPROVED** — never promote to HEALTHY |
| Merge of #770 / A1 tip | Owner | `MERGE_AUTHORIZATION = NOT_GRANTED` |
| Formal IV / verifier bind | Owner / estate | `EXTERNAL_IV_GATED` |
| Tauri / desktop shell | Deferred | Not required for A1 TECHNICALLY_COMPLETE |
| A2 first governed action | Scoped in `a2/` docs | Implementation **NOT_STARTED** |

## Non-claims

- Not merged to `main`.
- Not formal IV / CERTIFIED.
- No Studio mutation authority (`STUDIO_MUTATION_AUTHORITY = NONE`).
- No A2 claim/dispatch/handoff/worktree/terminal implementation in this closure.
- No `atlasd` binary required (O1).

## Architecture verdict

A1 remains the correct Mission Control layer: projection over A0 + F12/F15,
attention ≠ authorization, freshness honesty, unknown ≠ healthy, zero mutation
API. Adversarial semantic suite + agent/matrix mismatch binding make the
coherence claim defensible for `TECHNICALLY_COMPLETE / EXTERNAL_IV_GATED`.
