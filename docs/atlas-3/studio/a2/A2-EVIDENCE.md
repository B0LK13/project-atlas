# AS-STUDIO-A2-001 — evidence (Governed OWNERSHIP_CLAIM)

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE
FIRST_GOVERNED_ACTION = OWNERSHIP_CLAIM
PREVIEW != EXECUTION = ENFORCED
EXECUTION_TIME_REVALIDATION = FAIL_CLOSED
STUDIO_SELF_AUTHORIZATION = IMPOSSIBLE_WITHIN_PROVEN_SCOPE
DISPATCH = NOT_STARTED
STEAL_AUTO_EXECUTION = NOT_STARTED
MERGE_AUTHORIZATION = NOT_GRANTED
CI_PASS != FORMAL_IV
IMPLEMENTED != MERGED
```

## Exact objects

| Field | Value |
|---|---|
| Package | `AS-STUDIO-A2-001` |
| Branch | `feat/as-studio-a2-001` |
| Base | A1 tip / PR #770 |
| HEAD |  |
| Local tests | 59 passed (A0+A1+A2); ruff PASS; doctor PASS |
| Module | `scripts/atlas_studio/action_intent.py` |
| Schemas | `atlas_studio_action_{intent,preview,decision}_v1.schema.json` |
| CLI | `claim-candidates`, `claim-preview`, `claim-intent`, `claim-evaluate`, `claim-execute` |
| Tests | `tests/unit/test_atlas_studio_a2_governed_claim.py` |
| ADR | ADR-035 |

## Validation (lane)

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a{0,1,2}*.py \
  tests/unit/test_atlas_studio_a1_semantic_boundaries.py -q --tb=short --no-cov
# 59 passed (15 A0 + 15 A1 MC + 10 A1 semantic + 19 A2)
.venv/bin/python -m ruff check scripts/atlas_studio tests/unit/test_atlas_studio_a2_governed_claim.py
.venv/bin/python scripts/atlas-studio.py doctor --json
```

## Flow enforced

```text
MC truth → candidate (F12 OWNERSHIP_CLAIM) → preview → intent
→ evaluate (fresh revalidation) → execute|refuse via emitter OWNER_CLAIMED
→ decision evidence
```

## Refusal codes

`EXECUTED`, `REFUSED_STALE`, `REFUSED_ALREADY_OWNED`, `REFUSED_NOT_RUNNABLE`,
`REFUSED_AGENT_INVALID`, `REFUSED_CAPABILITY`, `REFUSED_POLICY`,
`REFUSED_TARGET_MISMATCH`, `REFUSED_IDEMPOTENT_ALREADY_CLAIMED`, `REFUSED_SCHEMA`

## Non-claims

No dispatch, steal auto-execution, merge, IV, handoff delivery, worktree, PTY.
A1 Mission Control remains usable without A2 mutation context.
