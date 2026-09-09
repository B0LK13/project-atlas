# AS-STUDIO-A2-001 — evidence (Governed OWNERSHIP_CLAIM + substrate)

```text
AS_STUDIO_A2_001 = IMPLEMENTED_IN_LANE
AS_STUDIO_A2_GOVERNANCE_SUBSTRATE = IMPLEMENTED_IN_LANE
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
| HEAD | (fill after push) |
| Local tests | A0+A1+A2+substrate; ruff PASS; doctor PASS |
| Modules | `scripts/atlas_studio/governance.py`, `action_intent.py` |
| Schemas | `atlas_studio_action_{intent,preview,decision}_v1.schema.json` |
| CLI | `claim-candidates`, `claim-preview`, `claim-intent`, `claim-evaluate`, `claim-execute` |
| Tests | `test_atlas_studio_a2_governed_claim.py`, `test_atlas_studio_a2_governance_substrate.py` |
| Docs | `A2-GOVERNANCE-SUBSTRATE.md` |
| ADR | ADR-035 |

## Validation (lane)

```bash
.venv/bin/python -m pytest tests/unit/test_atlas_studio_a{0,1,2}*.py \
  tests/unit/test_atlas_studio_a1_semantic_boundaries.py -q --tb=short --no-cov
.venv/bin/python -m ruff check scripts/atlas_studio \
  tests/unit/test_atlas_studio_a2_governed_claim.py \
  tests/unit/test_atlas_studio_a2_governance_substrate.py
.venv/bin/python scripts/atlas-studio.py doctor --json
```

## Flow enforced

```text
MC truth → candidate (F12 OWNERSHIP_CLAIM) → preview → intent
→ governance.evaluate_governed_intent → execute|refuse via emitter OWNER_CLAIMED
→ decision evidence
```

Claim is registered as the first `ActionHandler` instance; futures
(`CI_DISPATCH`, `IV_REQUEST`, `HANDOFF_DELIVER`, `STEAL_EXECUTE`, `MERGE`,
`WORKTREE_OPEN`) are declared `NOT_STARTED` and refuse closed.

## Refusal codes

`EXECUTED`, `REFUSED_STALE`, `REFUSED_ALREADY_OWNED`, `REFUSED_NOT_RUNNABLE`,
`REFUSED_AGENT_INVALID`, `REFUSED_CAPABILITY`, `REFUSED_POLICY`,
`REFUSED_TARGET_MISMATCH`, `REFUSED_IDEMPOTENT_ALREADY_CLAIMED`, `REFUSED_SCHEMA`,
`REFUSED_UNSUPPORTED_ACTION`

## Non-claims

No dispatch, steal auto-execution, merge, IV, handoff delivery, worktree, PTY.
A1 Mission Control remains usable without A2 mutation context.
Interface is not the source of authority.
